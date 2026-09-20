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
    expect( source ).toContain( '.trust-card{border:2px solid #d1f470;background:#fbfff0' );
    expect( source ).toContain( '.msg.sent{background:#d1f470' );
    expect( source ).toContain( '.tab.active{background:#d1f470;color:#1a3a2a}' );
    expect( source ).toContain( '.trust-badge{display:inline-block;background:#d1f470' );
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

  it( 'renders the Trusted by Meta section as two equal columns matching the page theme', () => {
    expect( source ).toContain( '.trust-grid{display:grid;grid-template-columns:1fr 1fr' );
    expect( source ).toContain( '.trust-card{border:2px solid #d1f470;background:#fbfff0' );
    expect( source ).toContain( '.trust-content{border:2px solid #e5e7eb;background:#fff' );
    expect( source ).toContain( '.trust-content:hover{border-color:#d1f470;background:#fbfff0;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}' );
    expect( source ).toContain( '.trust-badge{display:inline-block;background:#d1f470' );
    expect( source ).not.toContain( 'grid-template-columns:minmax(0,360px) 1fr' );
    expect( source ).not.toContain( '.trust-panel{' );
    expect( source ).not.toContain( '.meta-panel{background:#d1f470' );
    expect( source ).not.toContain( '.whatsapp-panel{background:#d1f470' );
  } );

  it( 'uses the agreed Trusted by Meta wording', () => {
    expect( source ).toContain( 'OFFICIAL META TECH PARTNER' );
    expect( source ).toContain( '<h2 className="trust-heading">Trusted by Meta</h2>' );
    expect( source ).toContain( 'Meta Tech Partner' );
    expect( source ).toContain( 'Customer engagement across WhatsApp, SMS, Email &amp; Voice — powered by Grahak OS.' );
    expect( source ).toContain( '<span className="pill">WhatsApp</span>' );
    expect( source ).toContain( '<span className="pill">Voice</span>' );
  } );
} );
