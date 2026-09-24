import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'public widgets final wiring', () => {
  const app = readFileSync( resolve( process.cwd(), 'src/pages/_app.tsx' ), 'utf8' );
  const lang = readFileSync( resolve( process.cwd(), 'src/components/LanguageBar.tsx' ), 'utf8' );

  it( 'shows the external WhatsApp widget on every public page, and never on the dashboard', () => {
    // Was gated to '/' and '/grahak-os' only. A help widget present on two pages and
    // absent on the other twelve reads as a bug: a visitor who sees it on the home page
    // and then wants it on a product or legal page finds it gone. Reusing isPublic - the
    // same gate as the public shell - also means a new public page gets the widget
    // automatically instead of needing this line edited.
    expect( app ).toContain( 'const showPublicWhatsApp = isPublic;' );
    expect( app ).not.toContain( "showPublicWhatsApp = router.pathname === '/'" );
    expect( app ).toContain( 'https://app.wecare.digital/stream/code/wecare-wa-widget.js' );
    // Still gated, not unconditional: the authenticated dashboard renders customer names,
    // numbers and message bodies, and a customer support widget there is pointed at the
    // wrong person.
    expect( app ).toContain( '{ showPublicWhatsApp && (' );
    expect( app ).not.toContain( 'PublicWhatsAppButton' );
    expect( existsSync( resolve( process.cwd(), 'src/components/PublicWhatsAppButton.tsx' ) ) ).toBe( false );
  } );

  it( 'aligns the language launcher with the WhatsApp button, and keeps the PANEL clear of it', () => {
    expect( lang ).toContain( 'className="language-trigger"' );

    // WHAT CHANGED, because this assertion has now been wrong in two different ways.
    //
    // It first checked for a bare 'right:16px' substring, which was a FALSE PASS: the
    // launcher had moved to right:96px and the only remaining 'right:16px' in the file sat
    // inside a comment describing the WhatsApp button's own position. The test stayed green
    // while testing nothing, which is why these assertions now pin whole rules.
    //
    // Then it pinned right:96px, which encoded the OLD strategy: push the entire cluster
    // sideways so nothing could ever overlap #wecarewa-widget. The owner asked for the two
    // floating icons to read as one set, so the strategy changed - the trigger now shares
    // the button's centre line and only the panel steps aside.
    //
    // The underlying constraint is untouched and is the reason the panel still moves:
    // #wecarewa-widget carries z-index 2147483647, the 32-bit maximum, so nothing can be
    // stacked above it. Overlap has to be avoided geometrically, not with z-index.
    expect( lang ).toContain( '.wc-langbar{position:fixed;right:20px;left:auto;bottom:52px' );

    // 56px matches the external icon's visible 56px circle; 20 + 28 puts both centres on
    // right:48px. Those two numbers are the whole alignment.
    expect( lang ).toContain( '.language-trigger{width:56px;height:56px' );

    // The panel is absolute and shifted left until its right edge clears the button's
    // x 16..80 column: 76px inside a container whose right edge is 20px out lands at 96px.
    expect( lang ).toContain( '.panel{position:absolute;right:76px;bottom:0' );
    expect( lang ).toContain( 'width:min(324px,calc(100vw - 116px))' );

    // 767px, not 600px - the external button switches to its mobile geometry at 767px, so
    // a 600px breakpoint here left the pair mismatched across 601..767px.
    expect( lang ).toContain( '@media(max-width:767px)' );

    // This file can only check that the strings are present. Whether the two circles
    // actually line up, and whether the open panel actually clears the button, is
    // geometry - measured by tools/browser/uicheck.js, which asserts equal diameter, a
    // shared centre line, an even gap, and x-clearance of the panel at four viewports.

    expect( lang ).toContain( 'className="panel-actions"' );
    expect( lang ).toContain( "speaking ? 'Stop' : 'Listen'" );
  } );
} );
