import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import * as customerAuth from '../lib/customerAuth';
import * as signInMessages from '../lib/signInMessages';
import SignIn from '../pages/account/sign-in';

/**
 * THE EMPTY-NUMBER TRAP on /account/sign-in - the defect the owner reported as "not able login".
 *
 * WHAT WAS WRONG, and why no existing test caught it. The number segment's placeholder was
 * `9876543210`: ten digits beginning with 9, which is a structurally valid Indian mobile number,
 * rendered in placeholder grey next to a segment already reading "+91 India". It reads as a number
 * that is ALREADY IN THE FIELD. A shopper who believes the field is filled presses the CTA, the
 * `required` constraint refuses the empty input, and the browser answers "Please fill out this
 * field." about a field that visibly contains a number.
 *
 * And because `required` makes the browser block submit, the page's own onSubmit never ran - so
 * composeE164's empty-number branch, and the approved BAD_NUMBER message it throws, were
 * UNREACHABLE. The only feedback was a transient native tooltip with no aria-invalid, no
 * aria-describedby and nothing left on screen once it dismissed.
 *
 * Every existing case in AccountSignIn.test.tsx types a value first, so all of them walked past
 * the one state the shopper was actually stuck in. These assert the state itself.
 *
 * WHAT THIS FILE CANNOT SEE. jsdom does not lay out or scroll, so the other half of the fix -
 * the fixed header covering the field when the browser reveals it - is not observable here. It is
 * pinned against the built artifact in SignInHeaderClearance.test.ts, which is the only layer
 * where a scroll offset exists at all.
 */

let navigatedTo: string;
beforeEach( () => {
  navigatedTo = '';
  // vi.restoreAllMocks() in beforeEach as well as afterEach, deliberately: a mock left behind by
  // an earlier file in the same worker would make these tests silently assert nothing. The prior
  // OTP work hit exactly that and recorded it.
  vi.restoreAllMocks();
  Object.defineProperty( window, 'location', {
    configurable: true,
    value: { ...window.location, search: '', assign: ( u: string ) => { navigatedTo = String( u ); }, replace: ( u: string ) => { navigatedTo = String( u ); } },
  } );
} );
afterEach( () => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
} );

function renderSignIn (): HTMLInputElement {
  vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
  vi.spyOn( customerAuth, 'restoreSession' ).mockResolvedValue( null );
  render( <SignIn /> );
  return screen.getByLabelText( 'WhatsApp number' ) as HTMLInputElement;
}

describe( 'the number field cannot be mistaken for a filled field', () => {
  it( 'does not advertise a placeholder that could be read as a real number', () => {
    const input = renderSignIn();
    const placeholder = String( input.getAttribute( 'placeholder' ) || '' );
    const digits = placeholder.replace( /\D/g, '' );

    // The field is genuinely empty - the grey text is a hint, nothing more.
    expect( input.value ).toBe( '' );
    // THE PROPERTY, NOT ONE SPELLING OF IT. Any mask whose digits could be dialled is the
    // defect, whatever its grouping, so this refuses the SHAPE rather than the old literal.
    // An Indian mobile number begins 6-9; a mask that cannot start a real number cannot be
    // read as one. `9876543210` fails this; `00000 00000` passes.
    expect( digits.length === 0 || /^[0-5]/.test( digits ) ).toBe( true );
    expect( placeholder ).not.toMatch( /^[6-9]\d{9}$/ );
  } );

  it( 'keeps the required constraint rather than trading it for a message', () => {
    // The inline error below is ADDED to the native behaviour, not substituted for it.
    // Removing `required` would also remove the "required" a screen reader announces.
    expect( renderSignIn().required ).toBe( true );
  } );
} );

describe( 'the browser refusing an empty number reaches the page error region', () => {
  it( 'shows the approved message, marks the field invalid and associates the two', async () => {
    const input = renderSignIn();
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' );

    // What the browser does when the CTA is pressed with the field empty: it blocks submit and
    // fires `invalid` on the offending control. jsdom does not run constraint validation on
    // submit, so the event is dispatched directly - the handler under test is the same one.
    fireEvent.invalid( input );

    const error = await screen.findByRole( 'alert' );
    expect( error.textContent ).toBe( signInMessages.BAD_NUMBER );
    // Not conveyed by colour alone, and not only by the transient native bubble: the input is
    // programmatically marked invalid and points at the message that explains why.
    await waitFor( () => expect( input.getAttribute( 'aria-invalid' ) ).toBe( 'true' ) );
    expect( String( input.getAttribute( 'aria-describedby' ) || '' ).split( /\s+/ ) ).toContain( error.id );
    // The hint stays in the description list, so it is not lost when the error appears.
    expect( input.getAttribute( 'aria-describedby' ) ).toContain( 'si-hint' );

    // And nothing was sent. An empty number must not reach the OTP front door.
    expect( requestOtp ).not.toHaveBeenCalled();
    expect( navigatedTo ).toBe( '' );
  } );

  it( 'uses a message already in the approved table, not a new string', async () => {
    const input = renderSignIn();
    fireEvent.invalid( input );
    const error = await screen.findByRole( 'alert' );
    // The owner's section-6 table is the only source of failure copy on this page. This asserts
    // the refusal did not introduce a seventh string, which is the drift the table exists to stop.
    expect( signInMessages.SECTION_6_MESSAGES ).toContain( error.textContent );
  } );

  it( 'still signs in normally once a number is entered', async () => {
    const input = renderSignIn();
    const requestOtp = vi.spyOn( customerAuth, 'requestOtp' ).mockResolvedValue( {
      session: 'sess-A', destination: '********3210', expiresInSeconds: 600, registered: true,
    } );

    fireEvent.invalid( input );
    await screen.findByRole( 'alert' );

    // The recovery path: the shopper types the number the error asked for. Ten national digits
    // plus the +91 the segment already carries must compose to ONE canonical E.164 - not a
    // doubled country code, and not a bare national number.
    fireEvent.change( input, { target: { value: '9123456789' } } );
    // Matched loosely on purpose. The pill's accessible name is its whole visible text
    // ("Sign in Send code") since the WCAG 2.5.3 fix removed the action-only aria-label,
    // and PillButtonAccessibleName.test.tsx is the test that owns that exact contract.
    // Re-pinning the full string here would make this test fail for a reason it is not about.
    fireEvent.click( screen.getByRole( 'button', { name: /Send code/ } ) );

    await waitFor( () => expect( requestOtp ).toHaveBeenCalledWith( '+919123456789' ) );
    expect( await screen.findByLabelText( 'WhatsApp code' ) ).toBeTruthy();
  } );
} );
