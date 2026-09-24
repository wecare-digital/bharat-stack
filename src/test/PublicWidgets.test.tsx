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

  it( 'keeps the language launcher icon-only, and clear of the WhatsApp button', () => {
    expect( lang ).toContain( 'className="language-trigger"' );
    // The full rule, not a bare 'right:16px' substring. That is what this assertion used
    // to check, and it was a FALSE PASS: the launcher moved to right:96px, while the only
    // remaining 'right:16px' in the file sits inside comments describing the WhatsApp
    // button's own position. The test stayed green while testing nothing.
    expect( lang ).toContain( '.wc-langbar{position:fixed;right:96px;left:auto;bottom:16px' );
    // 96px is not arbitrary: #wecarewa-widget is a 64x64 button at right:16px with
    // z-index 2147483647, the 32-bit maximum, so nothing can be stacked above it and the
    // launcher has to clear its 16px..80px column geometrically instead.
    expect( lang ).toContain( 'width:min(324px,calc(100vw - 108px))' );
    expect( lang ).toContain( 'className="panel-actions"' );
    expect( lang ).toContain( "speaking ? 'Stop' : 'Listen'" );
  } );
} );
