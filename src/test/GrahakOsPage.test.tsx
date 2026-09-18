import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'Grahak OS final public design', () => {
  const source = readFileSync( resolve( process.cwd(), 'src/pages/grahak-os/index.tsx' ), 'utf8' );

  it( 'uses the approved Meta and WhatsApp credential copy above the footer', () => {
    expect( source ).toContain( 'Meta Tech Provider' );
    expect( source ).toContain( 'Technology for WhatsApp business solutions' );
    expect( source ).toContain( 'Built on WhatsApp Business API' );
    expect( source ).toContain( 'Cloud API-powered messaging, automation and onboarding' );
    expect( source.indexOf( 'id="cta"' ) ).toBeLessThan( source.indexOf( 'id="trust-strip"' ) );
    expect( source ).toContain( 'id="metaBlue"' );
  } );

  it( 'uses Bharat Stack colors for general interaction states', () => {
    expect( source ).toContain( '.stat:hover{border-color:#d1f470' );
    expect( source ).toContain( '.pill:hover{border-color:#d1f470' );
    expect( source ).toContain( '.capability-card:hover{border-color:#d1f470' );
    expect( source ).toContain( '.mockup-wrapper:hover{border-color:#d1f470' );
    expect( source ).toContain( '.tab.active{background:#d1f470;color:#1a3a2a}' );
  } );

  it( 'uses clearer hero, stats and API messaging', () => {
    expect( source ).toContain( 'Reach customers across WhatsApp, SMS, Email & Voice' );
    expect( source ).toContain( 'Grahak OS unifies customer data, messaging, automation and campaigns in one customer engagement platform.' );
    expect( source ).toContain( '<span>4 Channels</span><small>WhatsApp, SMS, Email, Voice</small>' );
    expect( source ).toContain( '<span>Fast</span><small>Onboarding</small>' );
    expect( source ).toContain( '<span>Secure</span><small>APIs & customer engagement</small>' );
    expect( source ).toContain( 'Built for your stack' );
  } );

  it( 'includes Why Grahak OS and a real conversion CTA', () => {
    expect( source ).toContain( 'Why Grahak OS' );
    expect( source ).toContain( 'Unified customer data' );
    expect( source ).toContain( 'Intelligent orchestration' );
    expect( source ).toContain( 'Every channel in one platform' );
    expect( source ).toContain( 'Transform customer engagement with Grahak OS' );
    expect( source ).toContain( '>Start with WhatsApp<' );
    expect( source ).toContain( '>Talk to us<' );
  } );

  it( 'tightens capability descriptions and mobile typography', () => {
    expect( source ).toContain( 'One profile across every channel' );
    expect( source ).toContain( 'Coordinate WhatsApp, SMS, Email and Voice' );
    expect( source ).toContain( 'Secure APIs built to scale' );
    expect( source ).toContain( '.hero-left p{font-size:20px' );
    expect( source ).toContain( '.section-header p{font-size:20px' );
  } );
} );
