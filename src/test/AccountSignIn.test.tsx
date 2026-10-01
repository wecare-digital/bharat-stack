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

    // PINNED STRING CHANGED, DELIBERATELY. This asserted /was not right/i against "That code was
    // not right. Please try again." The owner's message table specifies the exact copy for each
    // failure, and for an invalid code with attempts remaining that is "Check your code." - so the
    // old assertion and the required string cannot both hold. The CONTRACT under test is unchanged:
    // a null from submitOtp means wrong code, attempts remain, invite a retry, do not navigate.
    expect( await screen.findByText( 'Check your code.' ) ).toBeTruthy();
    expect( navigatedTo ).toBe( '' );
  } );

  it( 'tells the shopper to send a new code when Cognito has failed the whole attempt', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    } );
    // cognito() in customerAuth.ts sets error.name from Cognito's __type. NotAuthorizedException on
    // a CUSTOM_AUTH challenge means the session is spent - another guess cannot succeed.
    const dead = new Error( 'Invalid session for the user.' );
    dead.name = 'NotAuthorizedException';
    vi.spyOn( customerAuth, 'submitOtp' ).mockRejectedValue( dead );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    await enterPhone();
    await enterCode( '000000' );

    expect( await screen.findByText( 'Code expired. Send a new one.' ) ).toBeTruthy();
    // NOT "check your code": a spent challenge cannot be fixed by retyping.
    expect( screen.queryByText( 'Check your code.' ) ).toBeNull();
    expect( navigatedTo ).toBe( '' );
  } );

  it( 'tells a throttled shopper to wait, never to send another code', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    } );
    const throttled = new Error( 'Too many requests' );
    throttled.name = 'TooManyRequestsException';
    vi.spyOn( customerAuth, 'submitOtp' ).mockRejectedValue( throttled );
    vi.stubGlobal( 'fetch', vi.fn() );

    render( <SignIn /> );
    await enterPhone();
    await enterCode( '000000' );

    // THE DISTINCTION THAT MATTERS. "Send a new one" to someone who is rate-limited walks them
    // straight back into the limit, so a throttle must not borrow the expiry message.
    expect( await screen.findByText( 'Wait before trying again.' ) ).toBeTruthy();
    expect( screen.queryByText( 'Code expired. Send a new one.' ) ).toBeNull();
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

    // PINNED STRING CHANGED, DELIBERATELY, for the same reason as /was not right/i above. This read
    // /was not accepted/i against "That code was not accepted. Please try again." A rejected
    // registration code with no explanatory status is, overwhelmingly, a mistyped one, so it takes
    // the table's invalid-code line. The contract under test - an error is shown, nothing navigates,
    // and sign-in is never attempted - is unchanged.
    expect( await screen.findByText( 'Check your code.' ) ).toBeTruthy();
    expect( navigatedTo ).toBe( '' );
    // Sign-in is never attempted when registration fails.
    expect( submitOtp ).not.toHaveBeenCalled();
  } );

  it( 'reads a 429 from the front door as a throttle, not as a bad code', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    const submitOtp = vi.spyOn( customerAuth, 'submitOtp' );
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, status: 200, json: async () => ( {} ) } )
      .mockResolvedValueOnce( { ok: false, status: 429, json: async () => ( {} ) } );
    vi.stubGlobal( 'fetch', fetchMock );

    render( <SignIn /> );
    await enterPhone();
    await enterCode( '123456' );

    expect( await screen.findByText( 'Wait before trying again.' ) ).toBeTruthy();
    expect( submitOtp ).not.toHaveBeenCalled();
  } );
} );

describe( 'the error copy is the owner\'s table and nothing else', () => {
  /**
   * THE HONESTY RULE, ASSERTED AS AN ABSENCE. "Use a WhatsApp number." is an approved string that
   * this page must NOT reach, because the only send-failure signal the backend offers today - the
   * registration front door's 502 {status:'send_failed'} - also covers a transient Meta outage. A
   * grep for the literal is the right instrument: any future edit that wires it up without first
   * wiring a provider signal that can prove it will fail here and have to justify itself.
   */
  it( 'never renders the WhatsApp-specific message for a generic send failure', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 502, json: async () => ( { status: 'send_failed' } ),
    } ) );

    render( <SignIn /> );
    await enterPhone();

    const alert = await screen.findByRole( 'alert' );
    expect( alert.textContent ).toBe( 'Couldn\u2019t send a code. Check your number.' );
    expect( alert.textContent ).not.toMatch( /WhatsApp/ );
  } );

  it( 'keeps the number-is-not-on-WhatsApp claim out of the rendered page entirely', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: '', destination: '', expiresInSeconds: 600, registered: false,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 502, json: async () => ( { status: 'send_failed' } ),
    } ) );

    const { container } = render( <SignIn /> );
    await enterPhone();
    await screen.findByRole( 'alert' );

    expect( container.textContent || '' ).not.toContain( 'Use a WhatsApp number.' );
  } );

  it( 'does not leak whether the number is already registered', async () => {
    /*
     * NON-ENUMERATION. The two paths diverge on `registered`, and a 502 can arrive on either. The
     * failure a shopper sees must therefore be identical in both, or the error message itself
     * becomes a way to ask "is this number a customer?".
     */
    const texts: string[] = [];
    for ( const registered of [ true, false ] )
    {
      vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
      vi.spyOn( customerAuth, 'requestOtp' ).mockRejectedValue(
        Object.assign( new Error( 'Rate exceeded' ), { name: 'TooManyRequestsException' } ),
      );
      vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
        ok: false, status: 429, json: async () => ( { registered } ),
      } ) );

      const { unmount } = render( <SignIn /> );
      await enterPhone();
      const alert = await screen.findByRole( 'alert' );
      texts.push( String( alert.textContent ) );
      unmount();
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    }
    expect( texts[ 0 ] ).toBe( texts[ 1 ] );
    expect( texts[ 0 ] ).toBe( 'Wait before trying again.' );
  } );
} );
