import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import PerksPage from '../pages/perks';

/**
 * /perks — a home-styled landing page (Section 4), and the repaired gift-card destination.
 *
 * WHAT THIS GUARDS, after the owner asked to (1) make /perks match the home page's look and its
 * animated/scroll-reveal treatment, and (2) remove the former gift-card / offers / rewards
 * sections and their anchors:
 *   - the hero reuses the shared RotatingHero the home page / /zip use (not a bespoke lookalike),
 *     so it owns the single <h1> and the single <main>;
 *   - the removed #gift-cards / #offers / #rewards sections and anchors are gone;
 *   - the scroll-reveal closing band ships its final visible state as the CSS default and only
 *     arms the entrance when it can animate, with reduced-motion handled (static export renders
 *     full content without JS);
 *   - no points / balances / history / live offers are invented;
 *   - no third-party gift-card provider name is ever surfaced;
 *   - no working-looking transacting control (buy / redeem / check-balance / apply) exists.
 * The active backend gift-card CTAs already point at https://wecare.digital/perks/ (the page,
 * not an anchor), so removing the anchors leaves no dead link — asserted below.
 */
describe( 'Perks page', () => {
  it( 'reuses the shared RotatingHero and owns a single h1 and single main', () => {
    const { container } = render( <PerksPage /> );

    // RotatingHero renders the one <main> and the one <h1>; the page must not add a second.
    expect( container.querySelectorAll( 'main' ) ).toHaveLength( 1 );
    const h1s = container.querySelectorAll( 'h1' );
    expect( h1s ).toHaveLength( 1 );

    // The hero badge keeps the customer-facing label "Perks".
    const text = container.textContent || '';
    expect( text ).toContain( 'Perks' );
  } );

  it( 'reuses RotatingHero (not a bespoke hero) and replicates the home scroll-reveal band', () => {
    const src = fs.readFileSync( path.join( process.cwd(), 'src/pages/perks.tsx' ), 'utf8' );
    // The sanctioned reuse surface, as on /zip, /shop, /blog and the product pages.
    expect( src ).toContain( "from '../components/RotatingHero'" );
    expect( src ).toContain( '<RotatingHero' );
    // The home page's one-shot scroll-reveal mechanism, armed via classList with the final state
    // shipped as the CSS default so it degrades to fully-visible without JS.
    expect( src ).toContain( 'IntersectionObserver' );
    expect( src ).toContain( 'is-armed' );
    expect( src ).toContain( 'threshold: 0.18' );
    // Reduced motion is honoured (both the JS early-return and a CSS media query).
    expect( src ).toContain( 'prefers-reduced-motion: reduce' );
    expect( src ).toContain( 'prefers-reduced-motion:reduce' );
  } );

  it( 'removed the gift-card, offers and rewards sections and their anchors', () => {
    const { container } = render( <PerksPage /> );
    expect( container.querySelector( '#gift-cards' ) ).toBeNull();
    expect( container.querySelector( '#offers' ) ).toBeNull();
    expect( container.querySelector( '#rewards' ) ).toBeNull();

    // The former non-transacting gift-card controls are gone entirely.
    expect( screen.queryByText( 'Buy a gift card' ) ).toBeNull();
    expect( screen.queryByText( 'Redeem a gift card' ) ).toBeNull();
    expect( screen.queryByText( 'Check balance' ) ).toBeNull();
  } );

  it( 'has no working-looking transacting control', () => {
    const { container } = render( <PerksPage /> );
    // No buttons at all. The only links are honest navigation to pages that already work; none
    // transacts and none carries a dead #gift-cards/#rewards/#offers anchor.
    expect( container.querySelectorAll( 'button' ) ).toHaveLength( 0 );
    for ( const a of Array.from( container.querySelectorAll( 'a' ) ) )
    {
      const href = a.getAttribute( 'href' ) || '';
      expect( href ).not.toContain( '#gift-cards' );
      expect( href ).not.toContain( '#rewards' );
      expect( href ).not.toContain( '#offers' );
    }
  } );

  it( 'invents no points, balances, history or live offers', () => {
    const { container } = render( <PerksPage /> );
    const text = ( container.textContent || '' ).toLowerCase();
    expect( text ).not.toMatch( /\d+\s*points/ );
    expect( text ).not.toMatch( /balance:\s*₹?\d/ );
    expect( text ).not.toContain( '₹' );
  } );

  it( 'never names a third-party gift-card provider', () => {
    const { container } = render( <PerksPage /> );
    const text = container.textContent || '';
    expect( text ).not.toMatch( /gift ?up/i );
  } );
} );

describe( 'the /gift-card references were repaired to a real destination', () => {
  const read = ( rel: string ): string =>
    fs.readFileSync( path.join( process.cwd(), rel ), 'utf8' );

  it( 'leaves no active gift-card CTA pointing at the dead /gift-card URL', () => {
    const files = [
      'amplify/functions/messaging/inbound-whatsapp-handler/handler.py',
      'amplify/functions/ai/ai-generate-response/handler.py',
      'amplify/functions/operations/seo-tools/wix.py',
    ];
    for ( const file of files )
    {
      expect( read( file ), file ).not.toContain( 'wecare.digital/gift-card' );
      expect( read( file ), file ).not.toContain( "'/gift-card'" );
    }
  } );

  it( 'points the whatsapp and AI gift-card CTAs at the real /perks page (no dead anchor)', () => {
    const whatsapp = read( 'amplify/functions/messaging/inbound-whatsapp-handler/handler.py' );
    expect( whatsapp ).toContain( 'https://wecare.digital/perks/' );
    // The destination is the page itself, not a removed in-page anchor.
    expect( whatsapp ).not.toContain( 'wecare.digital/perks/#gift-cards' );
    const ai = read( 'amplify/functions/ai/ai-generate-response/handler.py' );
    expect( ai ).toContain( 'https://wecare.digital/perks/' );
    expect( ai ).not.toContain( 'wecare.digital/perks/#gift-cards' );
  } );

  it( 'does not import chrome; reuses PageMeta and the shared hero', () => {
    const src = read( 'src/pages/perks.tsx' );
    expect( src ).toContain( "from '../components/PageMeta'" );
    expect( src ).toContain( "from '../components/RotatingHero'" );
    expect( src ).not.toMatch( /components\/(Header|Footer|SupportWidget|Layout)'/ );
  } );
} );
