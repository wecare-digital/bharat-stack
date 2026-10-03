import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';
import CheckoutProfile from '../components/CheckoutProfile';
import type { StoredAddress } from '../components/AddressFields';

/**
 * THE RESEND CONTROL, AND THE ONE QUESTION EVERY FAILURE ROW ANSWERS.
 *
 * Not "what went wrong" but **was a send consumed**. `otp_challenge.issue` persists `lastSentAt`
 * and `sendCount + 1` BEFORE `verification_email.send` runs, so:
 *
 *   - a 502 SEND_FAILED arrives with the server cooldown ALREADY running and one of five hourly
 *     sends already spent. Re-enabling the control immediately would buy a guaranteed 429 - a
 *     second dead end in place of the first - so it gets its own 60 s;
 *   - a 503 (either store) and a 500 fire BEFORE `issue`, so nothing was spent and no server
 *     cooldown exists. A client cooldown there would make a transient store outage look like rate
 *     limiting, so the control stays immediately available.
 *
 * The two 429 shapes are handled by ONE rule - any finite positive `retryAfterSeconds` - rather
 * than a list of error codes. `RESEND_TOO_SOON` comes from the challenge store and
 * `TOO_MANY_REQUESTS` from the per-phone and per-IP throttle, which is the axis actually bounding
 * abuse now that both WAF web ACLs are gone; keying on the hint covers a third shape without an
 * edit here. `RESEND_LIMIT_REACHED` is the exception precisely because it carries no hint: there
 * is no time to wait that helps within the window, so the control stops asking.
 *
 * Fake timers throughout, so the 60 s is asserted rather than waited for. `waitFor` and `findBy*`
 * are deliberately NOT used here: they poll on a timer this test controls. Microtasks are flushed
 * with the repo's existing `act( async () => Promise.resolve() )` shape (see VayuLokLive.test).
 */

const ADDRESS: StoredAddress = {
  addressLine1: '12 MG Road',
  addressLine2: '',
  locality: '',
  city: 'Bengaluru',
  state: 'Karnataka',
  postalCode: '560001',
  country: 'India',
  countryCode: 'IN',
  fullAddress: '12 MG Road, Bengaluru, Karnataka, 560001, India',
};

const INITIAL = {
  firstName: 'Asha',
  lastName: 'Sen',
  email: 'asha@example.com',
  address: ADDRESS,
};

interface Reply { ok: boolean; status?: number; payload?: Record<string, unknown> }

/** Replies in order; the last one repeats, so a test only states what it cares about. */
function stubRequests ( replies: Reply[] ) {
  let index = 0;
  const fetchMock = vi.fn( async () => {
    const reply = replies[ Math.min( index, replies.length - 1 ) ];
    index += 1;
    return {
      ok: reply.ok,
      status: reply.status === undefined ? ( reply.ok ? 200 : 500 ) : reply.status,
      json: async () => reply.payload || ( reply.ok ? { status: 'sent' } : {} ),
    };
  } );
  vi.stubGlobal( 'fetch', fetchMock );
  return fetchMock;
}

const flush = () => act( async () => { await Promise.resolve(); await Promise.resolve(); } );
const tick = ( ms: number ) => act( async () => { await vi.advanceTimersByTimeAsync( ms ); } );

const emailInput = () => screen.getByLabelText( 'Email' );
const sendControl = () => screen.getByRole( 'button', { name: /^Send (verification code by email|email code)/ } );
const resendControl = () => screen.getByRole( 'button', { name: /^Resend email code/ } );

function mount () {
  render( <CheckoutProfile accessToken="fixture-session" mode="email"
    initial={ INITIAL } onReady={ vi.fn() } /> );
  // A changed email is what requires a code at all, so every case here starts from one.
  fireEvent.change( emailInput(), { target: { value: 'new@example.com' } } );
}

afterEach( () => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
} );

describe( 'the resend control in the sent arm', () => {
  it( 'appears beside Verify, disabled, counting down from 60', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: true } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByLabelText( 'Email verification code' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'button', { name: 'Verify email code' } ) ).toBeInTheDocument();
    expect( resendControl() ).toBeDisabled();
    expect( resendControl() ).toHaveTextContent( 'Resend email code 60s' );
    expect( screen.getByText( 'Another code can be requested in 60s.' ) ).toBeInTheDocument();
  } );

  it( 'counts down once a second and re-enables itself when the cooldown expires', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: true } ] );
    mount();
    fireEvent.click( sendControl() );
    await flush();

    await tick( 1000 );
    expect( resendControl() ).toHaveTextContent( 'Resend email code 59s' );

    await tick( 17_000 );
    expect( resendControl() ).toHaveTextContent( 'Resend email code 42s' );
    expect( resendControl() ).toBeDisabled();

    await tick( 42_000 );
    expect( screen.getByRole( 'button', { name: 'Resend email code' } ) ).toBeEnabled();
    // The live region empties rather than announcing a stale number.
    expect( screen.queryByText( /Another code can be requested/ ) ).toBeNull();
  } );

  it( 'keeps the countdown in a polite live region and in the button text itself', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: true } ] );
    mount();
    fireEvent.click( sendControl() );
    await flush();

    const region = screen.getByText( 'Another code can be requested in 60s.' );
    expect( region ).toHaveAttribute( 'aria-live', 'polite' );
    // WCAG 2.5.3: the accessible name contains the visible label, because it IS the visible text.
    expect( resendControl() ).toHaveAccessibleName( 'Resend email code 60s' );
  } );
} );

describe( 'the two 429 shapes, which both carry a retry hint', () => {
  it( 'adopts retryAfterSeconds from RESEND_TOO_SOON and returns to Send verification code by email', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 429, payload: { error: 'RESEND_TOO_SOON', retryAfterSeconds: 25 } } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByText( 'Wait 25 seconds before asking for another code.' ) ).toBeInTheDocument();
    // Back to the Send verification code by email control: there is no code coming, so a code box would be a lie.
    expect( screen.queryByLabelText( 'Email verification code' ) ).toBeNull();
    expect( sendControl() ).toBeDisabled();
    expect( sendControl() ).toHaveTextContent( 'Send email code 25s' );

    await tick( 25_000 );
    expect( screen.getByRole( 'button', { name: 'Send verification code by email' } ) ).toBeEnabled();
  } );

  it( 'adopts retryAfterSeconds from TOO_MANY_REQUESTS when the resend itself is throttled', async () => {
    vi.useFakeTimers();
    stubRequests( [
      { ok: true },
      { ok: false, status: 429, payload: { error: 'TOO_MANY_REQUESTS', retryAfterSeconds: 40 } },
    ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();
    await tick( 60_000 );
    expect( screen.getByRole( 'button', { name: 'Resend email code' } ) ).toBeEnabled();

    fireEvent.click( resendControl() );
    await flush();

    expect( screen.getByText( 'Wait 40 seconds before asking for another code.' ) ).toBeInTheDocument();
    expect( sendControl() ).toBeDisabled();
    expect( sendControl() ).toHaveTextContent( 'Send email code 40s' );
  } );
} );

describe( 'the failures that differ on whether a send was consumed', () => {
  it( 'gives 502 SEND_FAILED its own 60 s, because the server cooldown is already running', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 502, payload: { error: 'SEND_FAILED' } } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByText(
      'We could not send the email code. You can ask for another in a moment.' ) ).toBeInTheDocument();
    expect( sendControl() ).toBeDisabled();
    expect( sendControl() ).toHaveTextContent( 'Send email code 60s' );

    await tick( 59_000 );
    expect( sendControl() ).toBeDisabled();

    await tick( 1_000 );
    expect( screen.getByRole( 'button', { name: 'Send verification code by email' } ) ).toBeEnabled();
  } );

  it( 'leaves the control immediately available after 503 TEMPORARILY_UNAVAILABLE', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 503, payload: { error: 'TEMPORARILY_UNAVAILABLE' } } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByText(
      'We could not reach the verification service. Try again.' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'button', { name: 'Send verification code by email' } ) ).toBeEnabled();
    expect( screen.queryByText( /Another code can be requested/ ) ).toBeNull();
  } );

  it( 'leaves the control immediately available after 500 INTERNAL_ERROR', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 500, payload: { error: 'INTERNAL_ERROR' } } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByText(
      'We could not reach the verification service. Try again.' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'button', { name: 'Send verification code by email' } ) ).toBeEnabled();
  } );
} );

describe( 'RESEND_LIMIT_REACHED, the one failure with no retry hint', () => {
  it( 'stops asking while leaving the email field editable', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 429, payload: { error: 'RESEND_LIMIT_REACHED' } } ] );
    mount();

    fireEvent.click( sendControl() );
    await flush();

    expect( screen.getByText( 'Too many codes requested. Try again later.' ) ).toBeInTheDocument();
    expect( sendControl() ).toBeDisabled();
    // No countdown, because no number of seconds helps inside the window.
    expect( sendControl() ).toHaveTextContent( 'Send verification code by email' );
    expect( screen.queryByText( /Another code can be requested/ ) ).toBeNull();

    // Waiting does not lift it either - only a different address has a different budget.
    await tick( 120_000 );
    expect( sendControl() ).toBeDisabled();

    expect( emailInput() ).not.toBeDisabled();
    expect( emailInput() ).not.toHaveAttribute( 'readonly' );
  } );

  it( 'lifts the block for a different address, whose hourly budget is its own', async () => {
    vi.useFakeTimers();
    stubRequests( [ { ok: false, status: 429, payload: { error: 'RESEND_LIMIT_REACHED' } } ] );
    mount();
    fireEvent.click( sendControl() );
    await flush();
    expect( sendControl() ).toBeDisabled();

    fireEvent.change( emailInput(), { target: { value: 'another@example.com' } } );
    expect( screen.getByRole( 'button', { name: 'Send verification code by email' } ) ).toBeEnabled();
  } );
} );
