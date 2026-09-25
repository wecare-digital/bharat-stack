import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'public widgets final wiring', () => {
  const app = readFileSync( resolve( process.cwd(), 'src/pages/_app.tsx' ), 'utf8' );
  const widget = readFileSync( resolve( process.cwd(), 'src/components/SupportWidget.tsx' ), 'utf8' );

  it( 'renders one combined widget and no longer loads the external WhatsApp script', () => {
    // WHAT CHANGED. The WhatsApp button used to be injected by a third-party script,
    // wecare-wa-widget.js on app.wecare.digital, gated behind a showPublicWhatsApp flag.
    // That put a green 56px circle at z-index 2147483647 - the maximum 32-bit integer -
    // which nothing could be stacked above, so this repo's own language panel had to be
    // shoved sideways to avoid being punched through. It was also the only off-palette
    // colour on every public page, and its size and icon were not ours to change.
    //
    // It is replaced by SupportWidget, which renders both actions itself.
    expect( app ).toContain( "import SupportWidget from '../components/SupportWidget'" );
    expect( app ).toContain( '<SupportWidget />' );

    // ASSERTED AGAINST CODE, NOT PROSE. A bare not.toContain('wecare-wa-widget.js') was
    // the first version and it failed on this file's own comments, which explain why the
    // script was retired - the guard cannot be allowed to fire on the note recording the
    // decision. So these pin the constructs that would actually load or gate it: the
    // <Script> tag's src and id, and an assignment to the old flag.
    expect( app ).not.toContain( 'src="https://app.wecare.digital/stream/code/wecare-wa-widget.js"' );
    expect( app ).not.toContain( 'id="wecare-wa-widget"' );
    expect( app ).not.toContain( 'const showPublicWhatsApp' );
    expect( app ).not.toContain( '{ showPublicWhatsApp && (' );

    // The old component name must be gone, not merely unused.
    expect( existsSync( resolve( process.cwd(), 'src/components/LanguageBar.tsx' ) ) ).toBe( false );
    expect( app ).not.toContain( '<LanguageBar' );
  } );

  it( 'keeps the WhatsApp link pointing where the external script pointed', () => {
    // Read out of the live wecare-wa-widget.js rather than invented, so retiring that
    // script does not silently move where visitors land.
    expect( widget ).toContain( 'https://wa.me/message/APDM5HUWH26SG1' );
    // An anchor, not a button with an onClick: it leaves the site, so it has to be
    // middle-clickable and copyable like any other link.
    expect( widget ).toContain( 'className="wc-wa"' );
    expect( widget ).toContain( 'rel="noopener noreferrer"' );
  } );

  it( 'presents both actions as one pill, in the site lime and smaller than before', () => {
    // One container holding both controls - previously two unrelated floating circles
    // with no shared colour, shape or container.
    expect( widget ).toContain( '.wc-pill{display:inline-flex' );
    expect( widget ).toContain( 'border:1.5px solid #d1f470' );
    // WhatsApp takes the palette's own-surface pairing, NOT WhatsApp green.
    expect( widget ).toContain( 'background:#d1f470;color:#1a3a2a' );
    expect( widget ).not.toContain( '#25D366' );
    // 40px controls, down from the 56px pair they replace.
    expect( widget ).toContain( '.wc-wa{width:40px;height:40px' );
    expect( widget ).toContain( '.language-trigger{width:40px;height:40px' );
  } );

  it( 'no longer works around a foreign stacking context', () => {
    // The panel opens above its own control now. It used to be pushed 76px left purely
    // to clear the external button in x, because z-index could not win against
    // 2147483647. With that button gone the workaround is unnecessary.
    expect( widget ).toContain( '.panel{position:absolute;right:0;bottom:100%' );
    expect( widget ).not.toContain( '.panel{position:absolute;right:76px' );
    // z-index only has to clear the mobile BottomNav (1200) and the header menu (1002).
    expect( widget ).toContain( 'z-index:1300' );
  } );

  it( 'survives the translation service being unavailable', () => {
    // THE REGRESSION THIS GUARDS. The component used to `return null` when fewer than
    // two languages loaded. Now that it also owns the WhatsApp button, that early return
    // would have taken customer support down with the translation API - so the catalogue
    // failing must hide the translate control only.
    expect( widget ).toContain( 'const canTranslate = langs.length >= 2' );
    expect( widget ).not.toContain( 'if ( langs.length < 2 ) return null' );
    // And it no longer hides itself on the home page, which is the most visited route.
    expect( widget ).not.toContain( "window.location.pathname === '/' ) return null" );
  } );

  it( 'mounts on the dashboard as well as the public pages', () => {
    // The widget is rendered in BOTH branches of _app.tsx - the public branch and the
    // authenticated one - so contact and language are available on every route in the
    // product, and a new page of either kind picks it up without being edited.
    // Counted on the JSX tag. Note the comments in _app.tsx deliberately refer to "the
    // SupportWidget component" in prose rather than writing the tag, precisely so this
    // count measures mounts and not explanatory text - the same trap that made an earlier
    // assertion in this file fire on a comment.
    const mounts = app.split( '<SupportWidget />' ).length - 1;
    expect( mounts, 'SupportWidget must be mounted in both the public and authenticated branches' ).toBe( 2 );
  } );

  it( 'cannot machine-translate customer data on the dashboard', () => {
    // THE HAZARD THIS PINS. The translator replaces text nodes in place. On the dashboard
    // those nodes are customer names, phone numbers, message bodies and invoice amounts -
    // translating them corrupts what an operator is reading and afterwards cannot be told
    // apart from real data. It is why the widget was previously kept off these screens.
    //
    // Two things make the mount safe, and BOTH have to hold:
    //   1. Layout marks the dashboard content container as no-translate. collectTextNodes
    //      rejects a node if any ancestor up to the root carries the attribute, so this
    //      exempts every dashboard page's content in one place.
    //   2. The widget starts its walk at `.layout`, which is above the sidebar, so the
    //      navigation still translates - the half that actually helps an operator.
    const layout = readFileSync( resolve( process.cwd(), 'src/components/Layout.tsx' ), 'utf8' );
    expect(
      layout,
      'Layout.tsx must mark .main-content as no-translate, or the dashboard mount lets an '
      + 'operator machine-translate live customer data'
    ).toContain( 'className="main-content" data-wc-no-translate="true"' );
    expect( widget ).toContain( "document.querySelector( '.layout' )" );

    // And the exemption has to be honoured by the walker itself.
    expect( widget ).toContain( "el.dataset.wcNoTranslate === 'true'" );
  } );

  it( 'keeps the translation panel behaviour it already had', () => {
    expect( widget ).toContain( 'className="language-trigger"' );
    expect( widget ).toContain( 'className="panel-actions"' );
    expect( widget ).toContain( "speaking ? 'Stop' : 'Listen'" );
    expect( widget ).toContain( '@media(max-width:767px)' );
  } );
} );
