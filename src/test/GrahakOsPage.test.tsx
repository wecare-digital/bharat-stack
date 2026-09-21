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

  it( 'uses the hosted Meta icon from app.wecare.digital', () => {
    expect( source ).toContain( 'src="https://app.wecare.digital/stream/media/m/meta-icon.svg"' );
    expect( source ).toContain( 'className="trust-mark meta-mark"' );
    expect( source ).not.toContain( 'src="/meta-icon.png"' );
  } );

  it( 'keeps the Meta card from stretching into a wide flat rectangle', () => {
    expect( source ).toContain( 'max-width:430px' );
    expect( source ).toContain( '.trust-card{border:2px solid #d1f470;background:#fbfff0;border-radius:20px;padding:48px 36px' );
  } );

  it( 'renders the Trusted by Meta section as two equal columns with an unboxed right half', () => {
    expect( source ).toContain( '.trust-grid{display:grid;grid-template-columns:1fr 1fr' );
    expect( source ).toContain( '.trust-card{border:2px solid #d1f470;background:#fbfff0' );
    expect( source ).toContain( '.trust-badge{display:inline-block;background:#d1f470' );
    // right half stays plain: no border, no background panel
    expect( source ).toContain( '.trust-content{display:flex;flex-direction:column;align-items:flex-start;gap:16px;min-width:0}' );
    expect( source ).not.toContain( 'grid-template-columns:minmax(0,360px) 1fr' );
    expect( source ).not.toContain( '.trust-content{border:' );
    expect( source ).not.toContain( '.trust-panel{' );
    expect( source ).not.toContain( '.meta-panel{background:#d1f470' );
    expect( source ).not.toContain( '.whatsapp-panel{background:#d1f470' );
  } );

  it( 'leaves no temporary design-review markup behind', () => {
    expect( source ).not.toContain( 'VARIANT' );
    expect( source ).not.toContain( 'tv-label' );
    expect( source ).not.toContain( 'tv-code' );
    expect( source ).not.toContain( 'TEMP DESIGN REVIEW' );
    // scroll-reveal animation restored on the section
    expect( source ).toContain( "className={`trust-strip anim ${show('trust-strip') ? 'show' : ''}`}" );
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
