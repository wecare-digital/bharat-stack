import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'support widget wiring', () => {
  const app = readFileSync( resolve( process.cwd(), 'src/pages/_app.tsx' ), 'utf8' );
  const widget = readFileSync( resolve( process.cwd(), 'src/components/SupportWidget.tsx' ), 'utf8' );

  it( 'renders one combined widget and no longer loads the external WhatsApp script', () => {
    // WHAT CHANGED. The WhatsApp button used to be injected by a third-party script,
    // wecare-wa-widget.js on app.wecare.digital, gated behind a showPublicWhatsApp flag.
    // That put a green 56px circle at z-index 2147483647 - the maximum 32-bit integer -
    // which nothing could be stacked above, so this repo's own language panel had to be
    // shoved sideways to avoid being punched through. It was also the only off-palette
    // colour on every public page, and its size and icon were not ours to change.
    expect( app ).toContain( "import SupportWidget from '../components/SupportWidget'" );
    expect( app ).toContain( '<SupportWidget />' );

    // ASSERTED AGAINST CODE, NOT PROSE. A bare not.toContain('wecare-wa-widget.js') was
    // the first version and it failed on this file's own comments, which explain why the
    // script was retired - the guard cannot be allowed to fire on the note recording the
    // decision. So these pin the constructs that would actually load or gate it.
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
    expect( widget ).toContain( '.wc-pill{position:relative;overflow:hidden;display:inline-flex' );
    expect( widget ).toContain( 'border:1.5px solid #d1f470' );
    // WhatsApp takes the palette's own-surface pairing, NOT WhatsApp green.
    expect( widget ).toContain( 'background:#d1f470;color:#1a3a2a' );
    expect( widget ).not.toContain( '#25D366' );
    // 40px controls, down from the 56px pair they replace.
    expect( widget ).toContain( '.wc-wa{width:40px;height:40px' );
    expect( widget ).toContain( 'height:40px' );
  } );

  it( 'uses a native select instead of a custom panel', () => {
    // The 324px panel - search field, ARIA combobox, scrolling listbox, keyboard
    // navigation, aria-activedescendant - is replaced by a real <select>. The platform
    // supplies all of that, and on a phone it opens the OS language picker.
    expect( widget ).toContain( '<select' );
    expect( widget ).toContain( 'aria-label="Choose language"' );
    expect( widget ).toContain( '.wc-chip{position:relative' );

    // The panel and its machinery must be GONE, not merely unused.
    //
    // PINNED ON CODE, NOT PROSE. A bare not.toContain('aria-activedescendant') failed on
    // the comment above the chip, which lists what the native control replaced - the guard
    // must not fire on the note explaining the deletion. So these match the JSX attribute
    // form (`aria-activedescendant={`) rather than the bare word.
    expect( widget ).not.toContain( 'className="panel' );
    expect( widget ).not.toContain( 'role="combobox"' );
    expect( widget ).not.toContain( 'aria-activedescendant={' );
    expect( widget ).not.toContain( 'className="language-trigger"' );

    // 16px on the select is not cosmetic: iOS Safari zooms the viewport when a focused
    // form control is smaller than that.
    expect( widget ).toContain( 'font-size:16px' );
  } );

  it( 'signals translating with lime motion, not a dark inversion', () => {
    // The chip used to flip to a #1a3a2a fill while working, which put the darkest object
    // on the page into the corner of every translation and read as an error rather than
    // as progress. The busy state is now lime-only and stays on the light surface: a
    // pulsing ring on the chip plus a sweep along the pill's bottom edge.
    expect( widget ).toContain( '@keyframes wc-ring' );
    expect( widget ).toContain( '@keyframes wc-sweep' );
    expect( widget ).toContain( '.wc-chip.is-busy{background:rgba(209,244,112,.38)' );
    // Specifically NOT the dark fill it used to take while busy.
    expect( widget ).not.toContain( "is-busy{background:#1a3a2a" );
    expect( widget ).not.toContain( "[aria-expanded='true']{background:#1a3a2a" );
    // Motion is slowed under reduced motion, never stopped: it is the only indication
    // that batches are still in flight, so freezing it would misreport a live translation
    // as a stalled one.
    expect( widget ).toContain( '@media(prefers-reduced-motion:reduce)' );
  } );

  it( 'has no read-aloud path left', () => {
    // READ-ALOUD IS REMOVED DELIBERATELY. Amazon Polly has no voice for Tamil, Telugu,
    // Bengali, Marathi, Gujarati, Kannada, Malayalam or Punjabi - its entire Indic
    // coverage is Hindi and Indian English - so the button was hidden for almost every
    // language this product serves. /tts responses were also never cached, making it the
    // largest cost line in the feature, and pre-generating audio is impossible for the
    // blog, /my-order and /get, which are dynamic.
    // PINNED ON CODE, NOT PROSE, for the same reason as the panel assertions above: the
    // header comment explains why /tts was dropped, so a bare not.toContain('/tts') fired
    // on the explanation. These match the fetch template and the JSX/identifier forms.
    expect( widget ).not.toContain( '${API_BASE}/tts' );
    expect( widget ).not.toContain( '${API_BASE}/voices' );
    expect( widget ).not.toContain( 'listen-btn' );
    expect( widget ).not.toContain( 'audioRef' );
    expect( widget ).not.toContain( 'new Audio(' );
    // `canSpeak` likewise survives only in the header comment recording why speech went,
    // so this pins the property access and the interface field rather than the bare word.
    expect( widget ).not.toContain( 'canSpeak:' );
    expect( widget ).not.toContain( '.canSpeak' );
    expect( widget ).not.toContain( 'setSpeaking' );
  } );

  it( 'mounts on every surface a visitor can land on', () => {
    // THREE MOUNTS, not two. _app.tsx has two route branches - public and authenticated -
    // but three places a human actually sees a page, and the third is easy to miss because
    // it is not a route: AuthGate, the sign-in screen. Every visitor without a session who
    // opens a staff URL lands there, and so does every mistyped path, since anything
    // outside the allowlist falls through to that branch.
    //
    // The gap that was fixed: AuthGate had Header and Footer but no SupportWidget, so the
    // one screen that tells somebody they cannot get in was also the one screen with no way
    // to contact us. Counting to 3 is what keeps it mounted there.
    //
    // Counted on the JSX tag. The comments in _app.tsx deliberately refer to "the
    // SupportWidget component" in prose rather than writing the tag, precisely so this
    // count measures mounts and not explanatory text.
    const mounts = app.split( '<SupportWidget />' ).length - 1;
    expect(
      mounts,
      'SupportWidget must be mounted in all three places a visitor can land: the public '
      + 'branch, the authenticated branch, and AuthGate (the sign-in screen)'
    ).toBe( 3 );
  } );

  it( 'cannot machine-translate customer data on the dashboard', () => {
    // THE HAZARD THIS PINS. The translator replaces text nodes in place. On the dashboard
    // those nodes are customer names, phone numbers, message bodies and invoice amounts -
    // translating them corrupts what an operator is reading and afterwards cannot be told
    // apart from real data. It is why the widget was previously kept off these screens.
    //
    // Two things make the mount safe, and BOTH have to hold:
    //   1. Layout marks the dashboard content container as no-translate. The walk rejects
    //      a node if any ancestor up to the root carries the attribute, so this exempts
    //      every dashboard page's content in one place.
    //   2. The widget starts its walk at `.layout`, above the sidebar, so navigation still
    //      translates - the half that actually helps an operator.
    const layout = readFileSync( resolve( process.cwd(), 'src/components/Layout.tsx' ), 'utf8' );
    expect(
      layout,
      'Layout.tsx must mark .main-content as no-translate, or the dashboard mount lets an '
      + 'operator machine-translate live customer data'
    ).toContain( 'className="main-content" data-wc-no-translate="true"' );
    expect( widget ).toContain( "document.querySelector( '.layout' )" );
    expect( widget ).toContain( "el.dataset.wcNoTranslate === 'true'" );
  } );

  it( 'survives the translation service being unavailable', () => {
    // THE REGRESSION THIS GUARDS. The component used to `return null` when fewer than two
    // languages loaded. Now that it also owns the WhatsApp button, that early return would
    // have taken customer support down with the translation API - so the catalogue failing
    // must hide the language chip only.
    expect( widget ).toContain( 'const canTranslate = langs.length >= 2' );
    expect( widget ).not.toContain( 'if ( langs.length < 2 ) return null' );
    // And it no longer hides itself on the home page, the most visited route.
    expect( widget ).not.toContain( "window.location.pathname === '/' ) return null" );
  } );
} );
