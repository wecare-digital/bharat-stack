import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import BlogContribution from '../components/BlogContribution';
import {
  CONTRIBUTION_PRESETS_PAISE,
  CONTRIBUTION_MIN_PAISE,
  CONTRIBUTION_MAX_PAISE,
  CONTRIBUTION_PURPOSE,
  paiseToRupees,
  rupeesToPaise,
  isAllowedContributionPaise,
} from '../config/contribution';

/**
 * THE "SUPPORT THIS WORK" CONTRIBUTION COMPONENT, IN ISOLATION.
 *
 * These cases pin the three things Section 5 is explicit about and that would regress silently:
 *   1. The preset amounts come from src/config/contribution.ts, not from literals in the markup.
 *   2. A custom amount is validated client-side against the configured bounds - out-of-range and
 *      non-numeric input is rejected and NOTHING is sent.
 *   3. With the backend gate off / unavailable / absent, the UI shows an honest non-error state
 *      and renders NO success affordance. A browser signal is never treated as proof of payment.
 */

afterEach( () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
} );

const renderBlock = () =>
  render( <BlogContribution postId="post-1" slug="a-clear-question" /> );

describe( 'BlogContribution presets', () => {
  it( 'renders every preset from the central config plus an Other option', () => {
    const { container } = renderBlock();
    const faces = Array.from( container.querySelectorAll( '.bc-choice-face' ) )
      .map( n => n.textContent || '' );

    // One face per preset, carrying the rupee value derived from the config's paise.
    for ( const paise of CONTRIBUTION_PRESETS_PAISE ) {
      expect( faces.some( f => f.includes( String( paiseToRupees( paise ) ) ) ) ).toBe( true );
    }
    // The owner's amounts, proving nothing re-typed a different number into the markup.
    // Changed from ₹49/₹99/₹199 to ₹200/₹400/₹600 on owner instruction (2026-10-02). These are
    // asserted as the FULL face text, not as substrings: the old test looked for '49', '99' and
    // '199', and '199' is a substring of nothing here while '99' would have matched a '₹990' face
    // just as happily - a loose check that could pass on the wrong number.
    expect( faces.join( ' ' ) ).toContain( '₹200' );
    expect( faces.join( ' ' ) ).toContain( '₹400' );
    expect( faces.join( ' ' ) ).toContain( '₹600' );
    // And the retired amounts must not still be on screen.
    expect( faces.join( ' ' ) ).not.toContain( '₹49' );
    expect( faces.join( ' ' ) ).not.toContain( '₹199' );
    expect( faces.some( f => f.includes( 'Other' ) ) ).toBe( true );

    // Presets + Other = one radio per choice.
    expect( container.querySelectorAll( 'input[type="radio"]' ) )
      .toHaveLength( CONTRIBUTION_PRESETS_PAISE.length + 1 );
  } );

  it( 'uses an h2 heading and the mandated primary copy, never an h1', () => {
    const { container } = renderBlock();
    expect( container.querySelector( 'h1' ) ).toBeNull();
    expect( container.querySelector( 'h2' )?.textContent ).toBe( 'Contribute' );
    expect( container.textContent ).toContain(
      'If you found this useful, you\u2019re welcome to make a small voluntary contribution.'
    );
  } );
} );

describe( 'BlogContribution custom-amount validation', () => {
  /**
   * The validation helpers are the single source of truth the component uses, so pinning them
   * here guarantees the UI and the config agree on what is in range.
   */
  it( 'rejects out-of-range and non-numeric custom amounts at the config boundary', () => {
    expect( isAllowedContributionPaise( CONTRIBUTION_MIN_PAISE ) ).toBe( true );
    expect( isAllowedContributionPaise( CONTRIBUTION_MAX_PAISE ) ).toBe( true );
    expect( isAllowedContributionPaise( CONTRIBUTION_MIN_PAISE - 1 ) ).toBe( false );
    expect( isAllowedContributionPaise( CONTRIBUTION_MAX_PAISE + 1 ) ).toBe( false );
    // Fractional paise is refused: the money core will not round it.
    expect( isAllowedContributionPaise( 4900.5 ) ).toBe( false );

    // rupeesToPaise refuses non-numeric, signed, and sub-paise entries.
    expect( rupeesToPaise( 'abc' ) ).toBeNull();
    expect( rupeesToPaise( '' ) ).toBeNull();
    expect( rupeesToPaise( '-5' ) ).toBeNull();
    expect( rupeesToPaise( '10.123' ) ).toBeNull();
    expect( rupeesToPaise( '49' ) ).toBe( 4900 );
    expect( rupeesToPaise( '49.50' ) ).toBe( 4950 );
  } );

  it( 'does not submit and shows a hint when the custom amount is out of range', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal( 'fetch', fetchMock );
    renderBlock();

    // Switch to the custom option, enter a below-minimum amount, submit.
    fireEvent.click( screen.getByDisplayValue( 'other' ) );
    const input = screen.getByLabelText( 'Amount in rupees' );
    fireEvent.change( input, { target: { value: '2' } } ); // ₹2 < ₹10 floor
    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).getAttribute( 'data-phase' ) ).toBe( 'invalid' );
    } );
    // The network was never touched, so an invalid amount cannot start a payment.
    expect( fetchMock ).not.toHaveBeenCalled();
  } );

  it( 'does not submit a non-numeric custom amount', async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal( 'fetch', fetchMock );
    renderBlock();

    fireEvent.click( screen.getByDisplayValue( 'other' ) );
    fireEvent.change( screen.getByLabelText( 'Amount in rupees' ), { target: { value: 'free!!' } } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).getAttribute( 'data-phase' ) ).toBe( 'invalid' );
    } );
    expect( fetchMock ).not.toHaveBeenCalled();
  } );
} );

describe( 'BlogContribution degrades honestly and never fabricates success', () => {
  it( 'sends the chosen preset, the purpose, postId and slug when a valid amount is submitted', async () => {
    const fetchMock = vi.fn().mockResolvedValue( {
      ok: true,
      json: async () => ( { state: 'PAYMENT_INITIATION_DISABLED' } ),
    } );
    vi.stubGlobal( 'fetch', fetchMock );
    renderBlock();

    // First preset is selected by default; submit it.
    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 1 ) );
    const [ , init ] = fetchMock.mock.calls[ 0 ];
    const body = JSON.parse( ( init as RequestInit ).body as string );
    expect( init ).toMatchObject( { method: 'POST' } );
    expect( body ).toMatchObject( {
      purpose: CONTRIBUTION_PURPOSE,
      postId: 'post-1',
      slug: 'a-clear-question',
      amountPaise: CONTRIBUTION_PRESETS_PAISE[ 0 ],
      currency: 'INR',
    } );
  } );

  it( 'shows an honest unavailable state when the backend gate is off', async () => {
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true,
      json: async () => ( { state: 'PAYMENT_INITIATION_DISABLED' } ),
    } ) );
    renderBlock();

    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).textContent )
        .toBe( 'Contributions are not available right now.' );
    } );
    const status = screen.getByRole( 'status' );
    expect( status.getAttribute( 'data-phase' ) ).toBe( 'unavailable' );
    // NO success affordance: no receipt, no thank-you, no "paid"/"verified" wording.
    expect( status.textContent?.toLowerCase() ).not.toMatch( /paid|verified|thank|receipt|success/ );
  } );

  it( 'shows the same honest state when the endpoint does not exist yet (404)', async () => {
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false,
      status: 404,
      json: async () => ( {} ),
    } ) );
    renderBlock();

    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).textContent )
        .toBe( 'Contributions are not available right now.' );
    } );
  } );

  it( 'shows the honest state on a network failure, never a success', async () => {
    vi.stubGlobal( 'fetch', vi.fn().mockRejectedValue( new Error( 'offline' ) ) );
    renderBlock();

    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).textContent )
        .toBe( 'Contributions are not available right now.' );
    } );
    expect( screen.getByRole( 'status' ).getAttribute( 'data-phase' ) ).toBe( 'unavailable' );
  } );

  it( 'treats CHECKOUT_REJECTED / CHECKOUT_AMBIGUOUS / unknown as unavailable, not success', async () => {
    for ( const state of [ 'CHECKOUT_REJECTED', 'CHECKOUT_AMBIGUOUS', 'SOMETHING_ELSE' ] ) {
      vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
        ok: true,
        json: async () => ( { state } ),
      } ) );
      const { unmount } = renderBlock();

      fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );
      await waitFor( () => {
        expect( screen.getByRole( 'status' ).getAttribute( 'data-phase' ) ).toBe( 'unavailable' );
      } );
      unmount();
      vi.unstubAllGlobals();
    }
  } );

  it( 'does not render a receipt even when the backend reports it is ready', async () => {
    // CHECKOUT_OPTIONS_READY means the server is live and issued a gateway order - it is NOT
    // proof of payment. The component may indicate it is opening a payment, but it must never
    // show a thank-you/receipt, which only an authoritative capture (FEAT-004) can justify.
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true,
      json: async () => ( {
        state: 'CHECKOUT_OPTIONS_READY',
        keyId: 'rzp_test_public',
        orderId: 'order_123',
        amountPaise: CONTRIBUTION_PRESETS_PAISE[ 0 ],
        currency: 'INR',
      } ),
    } ) );
    renderBlock();

    fireEvent.click( screen.getByRole( 'button', { name: 'Contribute' } ) );

    await waitFor( () => {
      expect( screen.getByRole( 'status' ).getAttribute( 'data-phase' ) ).toBe( 'ready' );
    } );
    const status = screen.getByRole( 'status' );
    // No fabricated success: "ready" never reads as paid/thank-you/verified.
    expect( status.textContent?.toLowerCase() ).not.toMatch( /paid|verified|thank|receipt|success/ );
  } );

  it( 'does not fetch at render time, so the static export is not broken', () => {
    const fetchMock = vi.fn();
    vi.stubGlobal( 'fetch', fetchMock );
    renderBlock();
    // The default server-rendered state is the available-presets form; a call happens only on a
    // user action, never during render/prerender.
    expect( fetchMock ).not.toHaveBeenCalled();
  } );
} );
