/**
 * TotpSetup — enrolment flow, and the two things that must never happen.
 *
 * The whole point of this component is that the shared secret is a credential.
 * So the assertions are not only "does the happy path work" but:
 *   1. the seed never reaches fetch/XHR/sendBeacon — no QR service, no analytics
 *   2. the seed is dropped from the DOM once verification succeeds
 *
 * It also pins the design values the owner asked for, because this screen was
 * built twice: first on the inner-page ladder (14px body, 13px radius) and then
 * corrected to the public contract (20px body, 50px pill). A test on the source
 * values is what stops it drifting back — the same approach GrahakOsPage.test.tsx
 * takes, and for the same reason.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';

const setUpTOTP = vi.fn();
const verifyTOTPSetup = vi.fn();
const updateMFAPreference = vi.fn();
const fetchMFAPreference = vi.fn();
const getCurrentUser = vi.fn();

vi.mock( 'aws-amplify/auth', () => ( {
  setUpTOTP: ( ...a: any[] ) => setUpTOTP( ...a ),
  verifyTOTPSetup: ( ...a: any[] ) => verifyTOTPSetup( ...a ),
  updateMFAPreference: ( ...a: any[] ) => updateMFAPreference( ...a ),
  fetchMFAPreference: ( ...a: any[] ) => fetchMFAPreference( ...a ),
  getCurrentUser: ( ...a: any[] ) => getCurrentUser( ...a ),
} ) );

// eslint-disable-next-line @typescript-eslint/no-var-requires
import TotpSetup, { groupSecret, hasTotp, isTotpPreferred, normaliseCode }
  from '../components/security/TotpSetup';

const SEED = 'JBSWY3DPEHPK3PXP';

function armSetup () {
  setUpTOTP.mockResolvedValue( {
    sharedSecret: SEED,
    getSetupUri: ( app: string, account: string ) =>
      new URL( `otpauth://totp/${app}:${account}?secret=${SEED}&issuer=${app}` ),
  } );
  getCurrentUser.mockResolvedValue( { username: 'wecare.digital' } );
}

describe( 'TotpSetup pure helpers', () => {
  it( 'groups the secret into readable runs without altering it', () => {
    expect( groupSecret( SEED ) ).toBe( 'JBSW Y3DP EHPK 3PXP' );
    expect( groupSecret( SEED ).replace( / /g, '' ) ).toBe( SEED );
    expect( groupSecret( '' ) ).toBe( '' );
  } );

  it( 'recognises TOTP under BOTH spellings, case-insensitively', () => {
    // Cognito reports SOFTWARE_TOKEN_MFA; Amplify has reported TOTP. Matching
    // only one is how an enrolled user gets told to enrol again.
    expect( hasTotp( { enabled: [ 'SOFTWARE_TOKEN_MFA' ] } ) ).toBe( true );
    expect( hasTotp( { enabled: [ 'TOTP' ] } ) ).toBe( true );
    expect( hasTotp( { enabled: [ 'totp' ] } ) ).toBe( true );
    expect( hasTotp( { enabled: [ 'EMAIL_OTP', 'SMS_MFA' ] } ) ).toBe( false );
    expect( hasTotp( null ) ).toBe( false );
  } );

  it( 'reads the preferred factor under both spellings', () => {
    expect( isTotpPreferred( { enabled: [], preferred: 'TOTP' } ) ).toBe( true );
    expect( isTotpPreferred( { enabled: [], preferred: 'SOFTWARE_TOKEN_MFA' } ) ).toBe( true );
    expect( isTotpPreferred( { enabled: [], preferred: 'EMAIL_OTP' } ) ).toBe( false );
    expect( isTotpPreferred( null ) ).toBe( false );
  } );

  it( 'keeps only six digits, stripping the spaces apps display', () => {
    expect( normaliseCode( '123 456' ) ).toBe( '123456' );
    expect( normaliseCode( '12345678' ) ).toBe( '123456' );
    expect( normaliseCode( 'abc12x3' ) ).toBe( '123' );
    expect( normaliseCode( '' ) ).toBe( '' );
  } );
} );

describe( 'TotpSetup flow', () => {
  beforeEach( () => {
    vi.clearAllMocks();
    Object.defineProperty( navigator, 'clipboard', {
      value: { writeText: vi.fn().mockResolvedValue( undefined ) },
      configurable: true,
    } );
  } );

  it( 'lists all three factors and offers enrolment when TOTP is absent', async () => {
    fetchMFAPreference.mockResolvedValue( {
      enabled: [ 'EMAIL_OTP', 'SMS_MFA' ], preferred: 'EMAIL_OTP',
    } );
    render( <TotpSetup /> );
    expect( await screen.findByText( 'Email' ) ).toBeInTheDocument();
    expect( screen.getByText( 'Text message' ) ).toBeInTheDocument();
    // Exactly once each. The card heading is "Register an authenticator app" so
    // it cannot collide with this row label, and the old standalone status badge
    // that repeated the TOTP state a second time was removed.
    expect( screen.getAllByText( 'Authenticator app' ) ).toHaveLength( 1 );
    expect( screen.getAllByText( 'Not registered' ) ).toHaveLength( 1 );
    expect( screen.getByRole( 'button', { name: /Add authenticator app/ } ) )
      .toBeInTheDocument();
  } );

  it( 'offers replacement, and no "not registered", when TOTP is already on',
    async () => {
      fetchMFAPreference.mockResolvedValue( {
        enabled: [ 'EMAIL_OTP', 'SOFTWARE_TOKEN_MFA' ], preferred: 'EMAIL_OTP',
      } );
      render( <TotpSetup /> );
      expect( await screen.findByRole( 'button', { name: /Replace authenticator app/ } ) )
        .toBeInTheDocument();
      // SMS is not in the enabled list here, so it is the only unregistered one.
      expect( screen.getAllByText( 'Not registered' ) ).toHaveLength( 1 );
    } );

  it( 'marks the default once, as a badge and not also as a dead button',
    async () => {
      fetchMFAPreference.mockResolvedValue( {
        enabled: [ 'EMAIL_OTP', 'SMS_MFA' ], preferred: 'EMAIL_OTP',
      } );
      render( <TotpSetup /> );
      expect( await screen.findByText( 'Default' ) ).toBeInTheDocument();
      expect( screen.getAllByText( 'Default' ) ).toHaveLength( 1 );
      // The default row offers no button. A disabled one repeating the word
      // reads like something is broken.
      expect( screen.queryByRole( 'button', { name: /^Default$/ } ) ).toBeNull();
    } );

  it( 'clears the default so sign-in asks each time', async () => {
    fetchMFAPreference.mockResolvedValue( {
      enabled: [ 'EMAIL_OTP', 'SMS_MFA' ], preferred: 'EMAIL_OTP',
    } );
    updateMFAPreference.mockResolvedValue( undefined );
    render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Ask me each time/ } ) );
    // Every ENROLLED factor is set NOT_PREFERRED. TOTP is absent from the call
    // because Cognito refuses a preference for a factor with nothing registered.
    await waitFor( () => expect( updateMFAPreference ).toHaveBeenCalledWith( {
      email: 'NOT_PREFERRED', sms: 'NOT_PREFERRED',
    } ) );
  } );

  it( 'makes a chosen factor the default without touching unenrolled ones',
    async () => {
      fetchMFAPreference.mockResolvedValue( {
        enabled: [ 'EMAIL_OTP', 'SMS_MFA' ], preferred: 'EMAIL_OTP',
      } );
      updateMFAPreference.mockResolvedValue( undefined );
      render( <TotpSetup /> );
      // Email is already the default so it has no button, and TOTP is not
      // registered so it has none either - the only "Make default" is SMS.
      const buttons = await screen.findAllByRole(
        'button', { name: /Make default/ } );
      expect( buttons ).toHaveLength( 1 );
      fireEvent.click( buttons[ 0 ] );
      await waitFor( () => expect( updateMFAPreference ).toHaveBeenCalledWith( {
        email: 'NOT_PREFERRED', sms: 'PREFERRED',
      } ) );
    } );

  it( 'offers no default button for a factor that is not registered', async () => {
    fetchMFAPreference.mockResolvedValue( {
      enabled: [ 'EMAIL_OTP' ], preferred: 'EMAIL_OTP',
    } );
    render( <TotpSetup /> );
    await screen.findByText( 'Authenticator app' );
    // TOTP and SMS are both unregistered, and neither may be made the default:
    // Cognito answers "User does not have delivery config set to turn on ..."
    // rather than silently accepting it, so the control is absent rather than
    // present-and-failing.
    expect( screen.queryAllByRole( 'button', { name: /Make default/ } ) )
      .toHaveLength( 0 );
    expect( screen.getAllByText( 'Not registered' ) ).toHaveLength( 2 );
  } );

  it( 'renders the grouped seed and a local otpauth:// link, never a remote URL',
    async () => {
      fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
      armSetup();
      render( <TotpSetup /> );
      fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );

      expect( await screen.findByLabelText( 'Authenticator setup key' ) )
        .toHaveTextContent( 'JBSW Y3DP EHPK 3PXP' );

      const link = screen.getByRole( 'link', { name: /open in your authenticator app/ } );
      const href = link.getAttribute( 'href' ) || '';
      // otpauth: is handled by an app on this device. Anything http(s) would be
      // shipping a live TOTP seed to a third party.
      expect( href.startsWith( 'otpauth://' ) ).toBe( true );
      expect( href ).not.toMatch( /^https?:/ );
    } );

  it( 'enables TOTP without touching the default factor unless asked', async () => {
    fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
    armSetup();
    verifyTOTPSetup.mockResolvedValue( undefined );
    updateMFAPreference.mockResolvedValue( undefined );

    render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );
    fireEvent.change( await screen.findByLabelText( /6-digit code/ ),
      { target: { value: '123456' } } );
    fireEvent.click( screen.getByRole( 'button', { name: /Confirm and turn on/ } ) );

    await waitFor( () => expect( verifyTOTPSetup ).toHaveBeenCalledWith( { code: '123456' } ) );
    expect( updateMFAPreference ).toHaveBeenCalledWith( { totp: 'ENABLED' } );
    expect( await screen.findByText( /Email remains your default/ ) ).toBeInTheDocument();
  } );

  it( 'only makes TOTP the default when the operator ticks the box', async () => {
    fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
    armSetup();
    verifyTOTPSetup.mockResolvedValue( undefined );
    updateMFAPreference.mockResolvedValue( undefined );

    render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );
    fireEvent.click( await screen.findByRole( 'checkbox' ) );
    fireEvent.change( screen.getByLabelText( /6-digit code/ ),
      { target: { value: '654321' } } );
    fireEvent.click( screen.getByRole( 'button', { name: /Confirm and turn on/ } ) );

    await waitFor( () =>
      expect( updateMFAPreference ).toHaveBeenCalledWith( { totp: 'PREFERRED' } ) );
  } );

  it( 'clears the seed from the DOM once verification succeeds', async () => {
    fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
    armSetup();
    verifyTOTPSetup.mockResolvedValue( undefined );
    updateMFAPreference.mockResolvedValue( undefined );

    const { container } = render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );

    // Awaited, not asserted synchronously: begin() is async, so the seed is not
    // in the tree on the tick after the click. And the probe is the code element
    // rather than container.textContent, which also contains the whole CSS block.
    const key = await screen.findByLabelText( 'Authenticator setup key' );
    expect( key ).toHaveTextContent( 'JBSW Y3DP EHPK 3PXP' );

    fireEvent.change( screen.getByLabelText( /6-digit code/ ),
      { target: { value: '123456' } } );
    fireEvent.click( screen.getByRole( 'button', { name: /Confirm and turn on/ } ) );

    await waitFor( () => expect( updateMFAPreference ).toHaveBeenCalled() );
    expect( screen.queryByLabelText( 'Authenticator setup key' ) ).toBeNull();
    expect( container.innerHTML ).not.toContain( SEED );
    expect( container.innerHTML ).not.toContain( 'JBSW' );
  } );

  it( 'does not send the seed to any network transport', async () => {
    fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
    armSetup();
    verifyTOTPSetup.mockResolvedValue( undefined );
    updateMFAPreference.mockResolvedValue( undefined );

    const fetchSpy = vi.fn().mockResolvedValue( { ok: true, json: async () => ( {} ) } );
    const beaconSpy = vi.fn().mockReturnValue( true );
    vi.stubGlobal( 'fetch', fetchSpy );
    vi.stubGlobal( 'navigator', Object.assign( navigator, { sendBeacon: beaconSpy } ) );

    render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );
    fireEvent.change( await screen.findByLabelText( /6-digit code/ ),
      { target: { value: '123456' } } );
    fireEvent.click( screen.getByRole( 'button', { name: /Confirm and turn on/ } ) );
    await waitFor( () => expect( updateMFAPreference ).toHaveBeenCalled() );

    for ( const spy of [ fetchSpy, beaconSpy ] )
    {
      for ( const call of spy.mock.calls )
      {
        expect( JSON.stringify( call ) ).not.toContain( SEED );
      }
    }
    vi.unstubAllGlobals();
  } );

  it( 'reports a mismatched code without losing the enrolment in progress', async () => {
    fetchMFAPreference.mockResolvedValue( { enabled: [ 'EMAIL_OTP' ] } );
    armSetup();
    verifyTOTPSetup.mockRejectedValue(
      Object.assign( new Error( 'nope' ), { name: 'CodeMismatchException' } ) );

    render( <TotpSetup /> );
    fireEvent.click( await screen.findByRole( 'button', { name: /Add authenticator app/ } ) );
    fireEvent.change( await screen.findByLabelText( /6-digit code/ ),
      { target: { value: '000000' } } );
    fireEvent.click( screen.getByRole( 'button', { name: /Confirm and turn on/ } ) );

    expect( await screen.findByText( /expire every 30 seconds/ ) ).toBeInTheDocument();
    // Still on the enrolment step, so the key is not re-issued and re-scanned.
    expect( screen.getByLabelText( 'Authenticator setup key' ) ).toBeInTheDocument();
    expect( updateMFAPreference ).not.toHaveBeenCalled();
  } );

  it( 'never puts a raw SDK error on screen when the factor read fails', async () => {
    fetchMFAPreference.mockRejectedValue(
      new Error( 'User wecare.digital is not authorized' ) );
    render( <TotpSetup /> );
    expect( await screen.findByText( /Could not read your current sign-in factors/ ) )
      .toBeInTheDocument();
    // The username must not leak through an error string.
    expect( screen.queryByText( /wecare\.digital/ ) ).toBeNull();
  } );
} );

describe( 'TotpSetup matches the PUBLIC design contract', () => {
  // Source-string assertions, the same technique as GrahakOsPage.test.tsx: these
  // exist to stop a value being changed incidentally. If you change one
  // deliberately, update the assertion and its comment.
  const src = fs.readFileSync(
    path.resolve( __dirname, '../components/security/TotpSetup.tsx' ), 'utf8' );

  it( 'uses the pill, not the inner 13px button', () => {
    expect( src ).toContain( 'padding:14px 28px' );
    expect( src ).toContain( 'border:2px solid #e5e7eb' );
    expect( src ).toContain( 'border-radius:50px' );
    expect( src ).toContain( 'font-size:17px' );
  } );

  it( 'swaps the border TO lime on hover, and never has lime at rest', () => {
    expect( src ).toContain( 'border-color:#d1f470' );
    expect( src ).toContain( 'box-shadow:0 4px 12px rgba(26,58,42,.12)' );
    expect( src ).not.toMatch( /border:\s*[\d.]+px solid #d1f470/ );
  } );

  it( 'holds the single 20px body level and the 22px card heading', () => {
    expect( src ).toContain( 'font-size:20px' );
    expect( src ).toContain( 'letter-spacing:-.125px' );
    expect( src ).toContain( 'rgba(0,0,0,.898)' );
    expect( src ).toContain( 'font-size:22px' );
    expect( src ).toContain( 'letter-spacing:-.25px' );
  } );

  it( 'renders the seed on a black code panel with the documented white stroke', () => {
    expect( src ).toContain( 'border:1.5px solid rgba(255,255,255,.92)' );
    expect( src ).toContain( 'background:#000' );
    expect( src ).toContain( 'border-radius:14px' );
  } );

  it( 'uses the static 1px hairline on the card, which has no hover', () => {
    expect( src ).toContain( 'border:1px solid #e5e7eb' );
  } );

  it( 'gives the affirmative badge lime fill with dark-green type and no border', () => {
    expect( src ).toContain( '.ts-mark-on{background:#d1f470;color:#1a3a2a}' );
  } );

  it( 'carries no retired colour', () => {
    for ( const dead of [ '#4b5563', '#111827', '#1e293b', '#0f172a', '#94a3b8',
      '#2f6b52', '#075e54', '#f2fbf6', '#fbfff0' ] )
    {
      expect( src ).not.toContain( dead );
    }
  } );

  it( 'opts its controls out of the inner-page !important overrides', () => {
    // Without data-public-ui, inner-pages.css rewrites the pill's radius,
    // padding, weight and border and no class selector can outrank it.
    expect( src ).toContain( 'data-public-ui' );
  } );

  it( 'does not letter-space or uppercase the label rung', () => {
    expect( src ).not.toContain( 'text-transform:uppercase' );
  } );
} );
