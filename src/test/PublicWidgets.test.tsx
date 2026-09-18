import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'public widgets', () => {
  const appPath = resolve( process.cwd(), 'src/pages/_app.tsx' );
  const langPath = resolve( process.cwd(), 'src/components/LanguageBar.tsx' );
  const waPath = resolve( process.cwd(), 'src/components/PublicWhatsAppButton.tsx' );

  it( 'uses a native WhatsApp button only for Home and Grahak OS', () => {
    const app = readFileSync( appPath, 'utf8' );
    expect( existsSync( waPath ) ).toBe( true );
    expect( app ).toContain( '<PublicWhatsAppButton />' );
    expect( app ).toContain( "const showPublicWhatsApp = router.pathname === '/' || router.pathname === '/grahak-os';" );
    expect( app ).not.toContain( 'wecare-wa-widget.js' );
  } );

  it( 'renders the language launcher as a right-side icon-only control', () => {
    const lang = readFileSync( langPath, 'utf8' );
    expect( lang ).toContain( 'className="language-trigger"' );
    expect( lang ).toContain( 'aria-label="Choose language"' );
    expect( lang ).toContain( 'right:16px' );
    expect( lang ).toContain( 'left:auto' );
    expect( lang ).toContain( 'className="panel-actions"' );
    expect( lang ).not.toContain( "selected?.native || selected?.name || 'English'" );
  } );

  it( 'keeps Listen inside the opened language panel', () => {
    const lang = readFileSync( langPath, 'utf8' );
    const panelStart = lang.indexOf( '<div className={ `panel ' );
    const panelEnd = lang.indexOf( '<div className="sr"' );
    const listen = lang.indexOf( "speaking ? 'Stop' : 'Listen'" );
    expect( panelStart ).toBeGreaterThanOrEqual( 0 );
    expect( listen ).toBeGreaterThan( panelStart );
    expect( listen ).toBeLessThan( panelEnd );
  } );
} );
