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
    expect( source ).toContain( 'Built on WhatsApp Business API' );
    expect( source ).toContain( 'trust-strip' );
    expect( source ).toContain( '.trust-grid{grid-template-columns:1fr}' );
    expect( source ).not.toContain( 'Meta Business Partners' );
  } );

  it( 'keeps hero stats in one desktop row and stacks them on mobile', () => {
    const source = readFileSync( pagePath, 'utf8' );
    expect( source ).toContain( '.hero-stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}' );
    expect( source ).toContain( '.hero-stats{grid-template-columns:1fr;gap:12px;width:100%}' );
  } );

  it( 'uses the WhatsApp green hover treatment across interactive surfaces', () => {
    const source = readFileSync( pagePath, 'utf8' );
    expect( source ).toContain( '.stat:hover{border-color:#075e54' );
    expect( source ).toContain( '.pill:hover{border-color:#075e54' );
    expect( source ).toContain( '.capability-card:hover{border-color:#075e54' );
    expect( source ).toContain( '.mockup-wrapper:hover{border-color:#075e54' );
  } );
} );
