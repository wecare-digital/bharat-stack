import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'public widgets final wiring', () => {
  const app = readFileSync( resolve( process.cwd(), 'src/pages/_app.tsx' ), 'utf8' );
  const lang = readFileSync( resolve( process.cwd(), 'src/components/LanguageBar.tsx' ), 'utf8' );

  it( 'restores the original external WhatsApp widget only on Home and Grahak OS', () => {
    expect( app ).toContain( "const showPublicWhatsApp = router.pathname === '/' || router.pathname === '/grahak-os';" );
    expect( app ).toContain( 'https://app.wecare.digital/stream/code/wecare-wa-widget.js' );
    expect( app ).not.toContain( 'PublicWhatsAppButton' );
    expect( existsSync( resolve( process.cwd(), 'src/components/PublicWhatsAppButton.tsx' ) ) ).toBe( false );
  } );

  it( 'keeps the language launcher icon-only on the right', () => {
    expect( lang ).toContain( 'className="language-trigger"' );
    expect( lang ).toContain( 'right:16px' );
    expect( lang ).toContain( 'left:auto' );
    expect( lang ).toContain( 'className="panel-actions"' );
    expect( lang ).toContain( "speaking ? 'Stop' : 'Listen'" );
  } );
} );
