import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { describe, expect, it } from 'vitest';

describe( 'Grahak OS five approved visual fixes', () => {
  const pagePath = resolve( process.cwd(), 'src/pages/grahak-os/index.tsx' );
  const source = readFileSync( pagePath, 'utf8' );

  it( 'drops the three hero stat cards and their dead CSS', () => {
    // Removed by design decision: the hero leads on the rotating channel pill,
    // so the stat row was redundant. Markup and styles both go.
    expect( source ).not.toContain( '<span>4 Channels</span>' );
    expect( source ).not.toContain( 'hero-stats' );
    expect( source ).not.toContain( '.stat{' );
    expect( source ).not.toContain( '.stat span{' );
    expect( source ).not.toContain( '.stat small{' );
    // the hero still leads with the cycling pill
    expect( source ).toContain( 'className="hero-cycle"' );
  } );

  it( 'uses the approved Bharat Stack lime and dark green color system', () => {
    expect( source ).toContain( '.phone-header{background:#1a3a2a' );
    expect( source ).toContain( '.avatar{width:40px;height:40px;background:#1a3a2a' );
    expect( source ).toContain( '.verified-badge{width:22px;height:22px;background:#1a3a2a' );
    expect( source ).toContain( '.msg.sent{background:#d1f470' );
    expect( source ).toContain( '.tab.active{background:#d1f470;color:#1a3a2a}' );
    // The Meta card is deliberately OUTSIDE the lime system. Framing another
    // company's logo in our own brand colour made a credential look like a sticker
    // we printed ourselves, so the card is neutral and the lime stays on our own
    // surfaces. Do not "restore" the tint.
    expect( source ).toContain( '.trust-card{border:1px solid rgba(0,0,0,.1);background:#fff' );
    expect( source ).not.toContain( '.trust-card{border:2px solid #d1f470' );
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
    expect( source ).toContain( '.trust-card{border:1px solid rgba(0,0,0,.1);background:#fff;border-radius:20px;padding:34px 30px' );
  } );

  it( 'states the Meta partnership once and carries substance, not padding', () => {
    // One logo lockup, one colour. The wordmark was dark green while the hosted
    // meta-icon.svg renders black, which is what made the lockup look broken.
    expect( source ).toContain( '.trust-wordmark{font-size:32px;font-weight:700;letter-spacing:-1px;color:#000}' );
    expect( source ).not.toContain( '.trust-wordmark{font-size:36px;font-weight:800;letter-spacing:-1px;color:#1a3a2a}' );
    // The card earns its space with what the partnership gives the customer.
    expect( source ).toContain( '<li>Official Cloud API access</li>' );
    expect( source ).toContain( '<li>Verified WABA provisioning</li>' );
    expect( source ).toContain( '<li>Green tick verification support</li>' );
    // The divider separates identity from substance; it used to split the lockup.
    expect( source ).toContain( '.trust-divider{width:100%;height:1px;background:rgba(0,0,0,.09)}' );
  } );

  it( 'renders the Trusted by Meta section as two equal columns with an unboxed right half', () => {
    expect( source ).toContain( '.trust-grid{display:grid;grid-template-columns:1fr 1fr' );
    expect( source ).toContain( '.trust-card{border:1px solid rgba(0,0,0,.1);background:#fff' );
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
    // The self-declared OFFICIAL META TECH PARTNER pill is gone. It restated the
    // card's own claim a third time in a single section, and a badge asserting
    // official status is the most legally exposed string on the page: Meta awards
    // that designation after review and it cannot be self-declared. The card states
    // the partnership once; the h2 makes the section's claim.
    expect( source ).not.toContain( 'OFFICIAL META TECH PARTNER' );
    expect( source ).not.toContain( 'trust-badge' );
    expect( source ).toContain( '<h2 className="trust-heading">Trusted by Meta</h2>' );
    expect( source ).toContain( 'Meta Tech Partner' );
    expect( source ).toContain( 'Customer engagement across WhatsApp, SMS, Email &amp; Voice — powered by Grahak OS.' );
    expect( source ).toContain( '<span className="pill">WhatsApp</span>' );
    expect( source ).toContain( '<span className="pill">Voice</span>' );
  } );
} );
