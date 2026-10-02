import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';

import PillButton from '../components/PillButton';

/**
 * The two-segment pill, the home-page phone-number treatment turned reusable and applied to every
 * customer login CTA. jsdom cannot compute styled-jsx, so the colours and the pill radius are the
 * browser harness's job; here we pin the two properties that keep the login flow and its tests
 * working no matter how the pill looks:
 *
 *   1. THE ACCESSIBLE NAME. The visible pill is two words, but the control must answer to the ACTION
 *      alone - that is the name AccountSignIn.test / CartCheckout.test query ("Send code",
 *      "Confirm code", "Proceed to checkout"). A regression here breaks the login tests silently, so
 *      it is asserted directly: the name is the action, or the ariaLabel override when given, and the
 *      static label is NOT part of it.
 *   2. REAL CONTROL SEMANTICS. A submit button submits, a disabled pill does not fire onClick, and an
 *      as="a" pill is a link with an href - the pill is a style on a real control, never a div.
 *
 * Plus a source-level check that the measured contrast tokens are the ones actually in the file, so
 * the dark-green/mint pair the briefing signed off on cannot drift to a failing shade unnoticed.
 */

afterEach( () => vi.restoreAllMocks() );

describe( 'the accessible name is the action, not the visible two-word pill', () => {
  it( 'answers to the action text alone, with the static label hidden from the name', () => {
    render( <PillButton label="Sign in" action="Send code" /> );
    // The pinned login query form: by role + exact action name.
    expect( screen.getByRole( 'button', { name: 'Send code' } ) ).toBeTruthy();
    // The label is decoration: it must not be concatenated into the name.
    expect( screen.queryByRole( 'button', { name: /Sign in Send code/ } ) ).toBeNull();
    // Both segments are still visible to sighted users.
    expect( screen.getByText( 'Sign in' ) ).toBeTruthy();
    expect( screen.getByText( 'Send code' ) ).toBeTruthy();
  } );

  it( 'lets ariaLabel set a name that differs from the shorter visible action (the cart case)', () => {
    render(
      <PillButton label="Checkout" action="Proceed" ariaLabel="Proceed to checkout" />,
    );
    // The cart test queries this exact name, while the pill only shows "Proceed".
    expect( screen.getByRole( 'button', { name: 'Proceed to checkout' } ) ).toBeTruthy();
    expect( screen.getByText( 'Proceed' ) ).toBeTruthy();
  } );
} );

describe( 'it is a real control, not a styled div', () => {
  it( 'renders a submit button when asked, so it drives a form submit', () => {
    const onSubmit = vi.fn( ( e: React.FormEvent ) => e.preventDefault() );
    render(
      <form onSubmit={ onSubmit }>
        <PillButton label="Sign in" action="Send code" type="submit" />
      </form>,
    );
    fireEvent.click( screen.getByRole( 'button', { name: 'Send code' } ) );
    expect( onSubmit ).toHaveBeenCalledTimes( 1 );
  } );

  it( 'does not fire onClick while disabled, and marks aria-busy when busy', () => {
    const onClick = vi.fn();
    render(
      <PillButton label="Sign in" action="Sending…" ariaLabel="Send code"
        onClick={ onClick } disabled busy />,
    );
    const button = screen.getByRole( 'button', { name: 'Send code' } );
    fireEvent.click( button );
    expect( onClick ).not.toHaveBeenCalled();
    expect( ( button as HTMLButtonElement ).disabled ).toBe( true );
    expect( button.getAttribute( 'aria-busy' ) ).toBe( 'true' );
  } );

  it( 'renders an anchor with an href when as="a"', () => {
    render( <PillButton as="a" href="/account/sign-in/" label="Sign in" action="Continue" /> );
    const link = screen.getByRole( 'link', { name: 'Continue' } );
    expect( link.getAttribute( 'href' ) ).toBe( '/account/sign-in/' );
  } );
} );

describe( 'the measured palette is the one in the file', () => {
  const SOURCE = readFileSync(
    join( __dirname, '..', 'components', 'PillButton.tsx' ), 'utf8',
  );

  it( 'uses the dark-green #1a3a2a edge/left segment and the passing mint #5fe3b0', () => {
    // #1a3a2a vs white is 12.48:1 (edge clears WCAG 1.4.11's 3:1), white-on-#1a3a2a is 12.48:1.
    expect( SOURCE ).toContain( '#1a3a2a' );
    // #5fe3b0 with #1a3a2a text is 7.79:1, which passes 4.5:1 - the site's base #3da35a would be
    // only 3.91:1, so the text-bearing segment must be the lighter mint.
    expect( SOURCE ).toContain( '#5fe3b0' );
    // A full pill radius, scoped so the global 13px in button.css cannot flatten it.
    expect( SOURCE ).toContain( 'border-radius:999px' );
    // Reduced motion is respected.
    expect( SOURCE ).toContain( 'prefers-reduced-motion' );
  } );
} );
