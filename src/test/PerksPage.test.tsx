import fs from 'node:fs';
import path from 'node:path';
import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import PerksPage from '../pages/perks';

/**
 * /perks — gift cards, rewards and offers (Section 4), and the repaired gift-card destination.
 *
 * WHAT THIS GUARDS. The owner's headline and the three section headings/copy are present; the
 * gift-card, rewards and offers controls are non-transacting (no backend exists), so they carry no
 * buy/redeem/check-balance link or button; no invented points/balances/offers appear; and no
 * third-party gift-card provider name is ever surfaced. The #gift-cards anchor must exist because
 * the header link and the repointed backend CTAs land there.
 */
describe( 'Perks page', () => {
  it( 'renders the owner headline and the three section headings', () => {
    const { container } = render( <PerksPage /> );
    const h1s = container.querySelectorAll( 'h1' );
    expect( h1s ).toHaveLength( 1 );
    expect( h1s[ 0 ].textContent ).toBe( 'A little extra, made for you.' );

    expect( screen.getByText( /Give them something they.?ll actually use\./ ) ).toBeInTheDocument();
    expect( screen.getByText( 'Something extra' ) ).toBeInTheDocument();
    expect( screen.getByText( 'More reasons to come back' ) ).toBeInTheDocument();

    // The owner's supporting copy for each section.
    expect( screen.getByText( /let them decide what comes next/i ) ).toBeInTheDocument();
    expect( screen.getByText( /apply eligible coupons during checkout/i ) ).toBeInTheDocument();

    expect( container.querySelectorAll( 'main' ) ).toHaveLength( 1 );
  } );

  it( 'exposes the #gift-cards anchor the header link and backend CTAs target', () => {
    const { container } = render( <PerksPage /> );
    expect( container.querySelector( '#gift-cards' ) ).not.toBeNull();
    expect( container.querySelector( '#rewards' ) ).not.toBeNull();
    expect( container.querySelector( '#offers' ) ).not.toBeNull();
  } );

  it( 'renders gift-card and rewards controls as non-transacting, with no live action', () => {
    const { container } = render( <PerksPage /> );

    // The gift-card options exist as text but are NOT links or buttons.
    for ( const label of [ 'Buy a gift card', 'Redeem a gift card', 'Check balance' ] )
    {
      expect( screen.getByText( label ) ).toBeInTheDocument();
      expect( screen.queryByRole( 'link', { name: new RegExp( label, 'i' ) } ) ).toBeNull();
      expect( screen.queryByRole( 'button', { name: new RegExp( label, 'i' ) } ) ).toBeNull();
    }

    // No interactive controls at all: nothing on this page can transact.
    expect( container.querySelectorAll( 'button' ) ).toHaveLength( 0 );
    expect( container.querySelectorAll( 'a' ) ).toHaveLength( 0 );

    // The non-transacting chips are marked disabled to assistive technology.
    expect( container.querySelectorAll( '.pk-chip[aria-disabled="true"]' ).length ).toBe( 3 );
  } );

  it( 'invents no points, balances, history or offers, and is honest when nothing is live', () => {
    const { container } = render( <PerksPage /> );
    const text = ( container.textContent || '' ).toLowerCase();
    // No fabricated reward state.
    expect( text ).not.toMatch( /\d+\s*points/ );
    expect( text ).not.toMatch( /balance:\s*₹?\d/ );
    expect( text ).not.toContain( '₹' );
    // Honest about the empty states.
    expect( text ).toContain( 'no live offers' );
    expect( text ).toContain( 'rewards are not available yet' );
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

  it( 'points the whatsapp and AI gift-card CTAs at the real /perks destination', () => {
    const whatsapp = read( 'amplify/functions/messaging/inbound-whatsapp-handler/handler.py' );
    expect( whatsapp ).toContain( 'https://wecare.digital/perks/' );
    const ai = read( 'amplify/functions/ai/ai-generate-response/handler.py' );
    expect( ai ).toContain( 'https://wecare.digital/perks/' );
  } );

  it( 'does not import chrome; reuses the shared band and PageMeta', () => {
    const src = read( 'src/pages/perks.tsx' );
    expect( src ).toContain( "from '../components/PageTopBand'" );
    expect( src ).toContain( "from '../components/PageMeta'" );
    expect( src ).not.toMatch( /components\/(Header|Footer|SupportWidget|Layout)'/ );
  } );
} );
