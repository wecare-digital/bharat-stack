import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'Grahak OS public page', () => {
  const pagePath = resolve( process.cwd(), 'src/pages/grahak-os/index.tsx' );

  it( 'physically hosts the customer engagement marketing experience', () => {
    expect( existsSync( pagePath ) ).toBe( true );
    if ( !existsSync( pagePath ) ) return;
    const source = readFileSync( pagePath, 'utf8' );
    expect( source ).toContain( 'Reach more customers' );
    expect( source ).toContain( 'Every touchpoint' );
    expect( source ).toContain( 'Built for the AI era' );
    expect( source ).toContain( 'Everything you need' );
  } );

  it( 'shows a coded responsive Meta and WhatsApp trust strip', () => {
    const source = readFileSync( pagePath, 'utf8' );
    expect( source ).toContain( 'Meta Tech Provider' );
    expect( source ).toContain( 'Built on WhatsApp Business Platform' );
    expect( source ).toContain( 'trust-strip' );
    expect( source ).toContain( '.trust-grid{grid-template-columns:1fr}' );
    expect( source ).not.toContain( 'Meta Business Partners' );
  } );
} );
