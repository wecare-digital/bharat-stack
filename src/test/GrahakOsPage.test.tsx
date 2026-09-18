import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'Grahak OS five approved visual fixes', () => {
  const pagePath = resolve( process.cwd(), 'src/pages/grahak-os/index.tsx' );
  const source = readFileSync( pagePath, 'utf8' );

  it( 'keeps hero stats compact and keeps 4 Channels together', () => {
    expect( source ).toContain( '<span>4 Channels</span>' );
    expect( source ).toContain( '.stat{background:#fff;border:2px solid #e5e7eb;border-radius:14px;padding:14px 16px' );
    expect( source ).toContain( '.stat span{display:block;font-size:22px' );
    expect( source ).toContain( 'white-space:nowrap' );
    expect( source ).not.toContain( 'min-height:112px' );
  } );

  it( 'uses the approved Bharat Stack lime and dark green color system', () => {
    expect( source ).toContain( '.phone-header{background:#1a3a2a' );
    expect( source ).toContain( '.avatar{width:40px;height:40px;background:#1a3a2a' );
    expect( source ).toContain( '.verified-badge{width:22px;height:22px;background:#1a3a2a' );
    expect( source ).toContain( '.meta-panel{background:#d1f470' );
    expect( source ).toContain( '.whatsapp-panel{background:#d1f470' );
    expect( source ).toContain( '.msg.sent{background:#d1f470' );
    expect( source ).toContain( '.tab.active{background:#d1f470;color:#1a3a2a}' );
    expect( source ).toContain( '.whatsapp-mark{color:#075e54}' );
    expect( source ).not.toContain( '#2f6b52' );
    expect( source ).not.toContain( '.verified-badge{width:22px;height:22px;background:#075e54' );
    expect( source ).not.toContain( '.meta-panel{background:#d9fbf2' );
    expect( source ).not.toContain( '.whatsapp-panel{background:#25d366' );
  } );

  it( 'removes both added CTA buttons', () => {
    expect( source ).not.toContain( '>Start with WhatsApp<' );
    expect( source ).not.toContain( '>Talk to us<' );
    expect( source ).not.toContain( 'className="cta-actions"' );
  } );

  it( 'uses the approved Meta icon from app.wecare.digital', () => {
    expect( source ).toContain( '<img className="trust-mark meta-mark" src="https://app.wecare.digital/stream/media/m/meta-icon.svg" alt="Meta" />' );
    expect( source ).not.toContain( 'src="/meta-icon.png"' );
  } );

  it( 'keeps the flat split credential strip', () => {
    expect( source ).toContain( '.trust-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:0' );
    expect( source ).toContain( '.meta-panel{background:#d9fbf2' );
    expect( source ).toContain( '.whatsapp-panel{background:#25d366' );
    expect( source ).not.toContain( 'box-shadow:0 8px 24px' );
  } );

  it( 'keeps the agreed credential wording', () => {
    expect( source ).toContain( 'Meta Tech Provider' );
    expect( source ).toContain( 'Technology for WhatsApp business solutions' );
    expect( source ).toContain( 'Built on WhatsApp Business API' );
    expect( source ).toContain( 'Cloud API-powered messaging, automation and onboarding' );
  } );
} );
