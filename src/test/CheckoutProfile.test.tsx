import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import CheckoutProfile from '../components/CheckoutProfile';

afterEach( () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
} );

describe( 'CheckoutProfile', () => {
  it( 'treats WhatsApp as already verified by sign-in', () => {
    render( <CheckoutProfile accessToken="fixture-session" onReady={ vi.fn() } /> );
    expect( screen.getByText( '✓ WhatsApp verified by sign-in' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'First name' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Last name' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Email' ) ).toBeInTheDocument();
    expect( screen.queryByLabelText( /WhatsApp number/i ) ).toBeNull();
  } );

  it( 'verifies email then saves only the narrow profile body', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, json: async () => ( { status: 'sent' } ) } )
      .mockResolvedValueOnce( {
        ok: true,
        json: async () => ( { status: 'VERIFIED', proof: 'fixture-proof' } ),
      } )
      .mockResolvedValueOnce( {
        ok: true,
        json: async () => ( {
          status: 'PROFILE_READY',
          contactId: 'contact-1',
          name: 'Asha Sen',
          email: 'asha@example.com',
          phone: '+919330994400',
        } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );
    const onReady = vi.fn();

    render( <CheckoutProfile accessToken="fixture-session" onReady={ onReady } /> );
    fireEvent.change( screen.getByLabelText( 'First name' ), { target: { value: 'Asha' } } );
    fireEvent.change( screen.getByLabelText( 'Last name' ), { target: { value: 'Sen' } } );
    fireEvent.change( screen.getByLabelText( 'Email' ), { target: { value: 'asha@example.com' } } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 1 ) );
    expect( String( fetchMock.mock.calls[ 0 ][ 0 ] ) ).toContain( '/auth/email-verification' );

    fireEvent.change( await screen.findByLabelText( 'Email verification code' ), {
      target: { value: '123456' },
    } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Verify' } ) );
    await screen.findByText( '✓ Email verified' );

    fireEvent.click( screen.getByRole( 'button', { name: /Save & continue/ } ) );
    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 3 ) );

    const [ url, init ] = fetchMock.mock.calls[ 2 ];
    expect( String( url ) ).toContain( '/customer/profile' );
    const body = JSON.parse( init.body );
    expect( body ).toEqual( {
      firstName: 'Asha',
      lastName: 'Sen',
      email: 'asha@example.com',
      emailProof: 'fixture-proof',
    } );
    expect( init.body ).not.toMatch( /phone|tags|optIn|allowlist/ );
    expect( onReady ).toHaveBeenCalledTimes( 1 );
  } );

  it( 'changing email invalidates a completed verification', async () => {
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, json: async () => ( { status: 'sent' } ) } )
      .mockResolvedValueOnce( {
        ok: true,
        json: async () => ( { status: 'VERIFIED', proof: 'fixture-proof' } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );

    render( <CheckoutProfile accessToken="fixture-session" onReady={ vi.fn() } /> );
    fireEvent.change( screen.getByLabelText( 'First name' ), { target: { value: 'Asha' } } );
    fireEvent.change( screen.getByLabelText( 'Last name' ), { target: { value: 'Sen' } } );
    fireEvent.change( screen.getByLabelText( 'Email' ), { target: { value: 'asha@example.com' } } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );
    fireEvent.change( await screen.findByLabelText( 'Email verification code' ), {
      target: { value: '123456' },
    } );
    fireEvent.click( screen.getByRole( 'button', { name: 'Verify' } ) );
    await screen.findByText( '✓ Email verified' );

    fireEvent.change( screen.getByLabelText( 'Email' ), { target: { value: 'new@example.com' } } );
    expect( screen.queryByText( '✓ Email verified' ) ).toBeNull();
    expect( screen.getByRole( 'button', { name: /Save & continue/ } ) ).toBeDisabled();
  } );

  it( 'does not treat purchase identity as marketing consent', () => {
    render( <CheckoutProfile accessToken="fixture-session" onReady={ vi.fn() } /> );
    expect( screen.getByText( /does not automatically opt you into marketing/i ) ).toBeInTheDocument();
  } );
} );
