import React from 'react';
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import * as customerAuth from '../lib/customerAuth';
import SignIn from '../pages/account/sign-in';

/**
 * The /account/sign-in OTP sign-in / register page, tested the way CartCheckout.test.tsx tests the
 * cart: against a mocked customerAuth and a mocked fetch (the registration front door), asserting
 * the control flow and DOM presence only. jsdom cannot read computed styles, so the design system
 * is left to the browser harnesses; here we prove the two-codes-not-one CONTRACT.
 *
 * The load-bearing property: on the REGISTER path the shopper answers TWO different codes - the
 * registration front-door code (verify), then the SECOND code the Cognito CUSTOM_AUTH sign-in
 * sends. The old code replayed the first code against the second challenge and could never sign a
 * new customer in; these tests fail against that logic and pass once the second code is collected.
 */

/** Capture where the page tries to navigate, without jsdom's "not implemented" throw. */
let navigatedTo: string;

beforeEach( () => {
  navigatedTo = '';
  Object.defineProperty( window, 'location', {
    configurable: true,
    value: {
      ...window.location,
      search: '',
      assign: ( url: string ) => { navigatedTo = String( url ); },
      replace: ( url: string ) => { navigatedTo = String( url ); },
    },
  } );
} );

afterEach( () => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
} );

/** Type the number and click "Send code". */
async function enterPhone ( value = '9876543210' ): Promise<void> {
  fireEvent.change( screen.getByLabelText( 'Mobile number' ), { target: { value } } );
  fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );
}

/** Type a code and click "Confirm code". */
async function enterCode ( value: string ): Promise<void> {
  fireEvent.change( await screen.findByLabelText( 'WhatsApp code' ), { target: { value } } );
  fireEvent.click( screen.getByRole( 'button', { name: 'Confirm code' } ) );
}

describe( 'the registered happy path', () => {
  it( 'answers the live Cognito challenge and redirects to the return path', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    } );
    const submitOtp = vi.spyOn( customerAuth, 'submitOtp' ).mockResolvedValue( {
      accessToken: 'tok-1', expiresAt: Date.now() + 3_600_000,
    } );
    const fetchMock = vi.fn();
    vi.stubGlobal( 'fetch', fetchMock );
    ( window.location as unknown as { search: string } ).search = '?return=/cart/';

    render( <SignIn /> );
    await enterPhone();
    await enterCode( '111111' );

    await waitFor( () => expect( navigatedTo ).toBe( '/cart/' ) );
    // The registered path never touches the registration front door.
    expect( fetchMock ).not.toHaveBeenCalled();
    // The code was answered against the session requestOtp handed back, not a second challenge.
    expect( requestOtp ).toHaveBeenCalledTimes( 1 );
    expect( submitOtp ).toHaveBeenCalledWith( '+919876543210', '111111', 'sess-A' );
  } );

  it( 'invites a retry when the code is wrong (submitOtp returns null) and does not navigate', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    } );
    vi.spyOn( customerAuth, 'submitOtp' ).mockResolvedValue( null );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    await enterPhone();
    await enterCode( '000000' );

    expect( await screen.findByText( /was not right/i ) ).toBeTruthy();
    expect( navigatedTo ).toBe( '' );
  } );
} );

describe( 'the register-then-sign-in path (two codes, not one)', () => {
  it( 'verifies the front-door code, then answers the SECOND Cognito code and redirects', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' )
      // First call: number is unknown -> route to registration.
      .mockResolvedValueOnce( {
        session: '', destination: '', expiresInSeconds: 600, registered: false,
      } )
      // Second call: after registration, the Cognito sign-in challenge (sends the SECOND code).
      .mockResolvedValueOnce( {
        session: 'sess-COGNITO', destination: '********3210', expiresInSeconds: 600, registered: true,
      } );
    const submitOtp = vi.spyOn( customerAuth, 'submitOtp' ).mockResolvedValue( {
      accessToken: 'tok-2', expiresAt: Date.now() + 3_600_000,
    } );
    // The registration front door: both request and verify succeed.
    const fetchMock = vi.fn().mockResolvedValue( { ok: true, json: async () => ( {} ) } );
    vi.stubGlobal( 'fetch', fetchMock );

    render( <SignIn /> );
    await enterPhone();

    // No OTP box was falsely labelled "we sent a code" for the unknown number; the register-code
    // step is reached only after the front-door request succeeds.
    await enterCode( 'REG-CODE' );

    // After verify, the page must move to the sign-in code step and prompt for a NEW code.
    expect( await screen.findByText( /all set up/i ) ).toBeTruthy();

    // The shopper enters the SECOND, different code Cognito sent.
    await enterCode( 'COGNITO-CODE' );

    await waitFor( () => expect( navigatedTo ).toBe( '/cart/' ) );

    // The front door was hit twice: request then verify.
    const bodies = fetchMock.mock.calls.map(
      ( c ) => JSON.parse( ( c[ 1 ] as RequestInit ).body as string ),
    );
    expect( bodies[ 0 ] ).toMatchObject( { action: 'request', phone: '+919876543210' } );
    expect( bodies[ 1 ] ).toMatchObject( { action: 'verify', phone: '+919876543210', code: 'REG-CODE' } );

    // The CRITICAL assertion: submitOtp is answered with the SECOND Cognito code against the
    // Cognito session - NOT the registration code. The old replay logic passed 'REG-CODE' here.
    expect( submitOtp ).toHaveBeenCalledTimes( 1 );
    expect( submitOtp ).toHaveBeenCalledWith( '+919876543210', 'COGNITO-CODE', 'sess-COGNITO' );
    // requestOtp is called twice: the initial probe and the post-registration sign-in challenge.
    expect( requestOtp ).toHaveBeenCalledTimes( 2 );
  } );

  it( 'surfaces an error when the front-door verify is rejected and does not sign in', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    const submitOtp = vi.spyOn( customerAuth, 'submitOtp' );
    // request ok, verify rejected.
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, json: async () => ( {} ) } )
      .mockResolvedValueOnce( { ok: false, json: async () => ( {} ) } );
    vi.stubGlobal( 'fetch', fetchMock );

    render( <SignIn /> );
    await enterPhone();
    await enterCode( 'WRONG' );

    expect( await screen.findByText( /was not accepted/i ) ).toBeTruthy();
    expect( navigatedTo ).toBe( '' );
    // Sign-in is never attempted when registration fails.
    expect( submitOtp ).not.toHaveBeenCalled();
  } );
} );
