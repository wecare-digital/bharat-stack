import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import PillButton from '../components/PillButton';

/**
 * WCAG 2.5.3 LABEL IN NAME, ASSERTED AS A PROPERTY RATHER THAN AS TODAY'S STRINGS.
 *
 * THE CRITERION. For a control whose label includes text, the accessible name must CONTAIN that
 * visible text. Level A. The two-segment pill used to fail it outright: both segments were
 * `aria-hidden` and the control carried an `aria-label` of the action alone, so a pill reading
 * "Sign in | Confirm code" announced only "Confirm code", and "Checkout | Proceed" announced
 * "Proceed to checkout" - a name containing neither visible word in order.
 *
 * WHO IT BROKE. Speech-input users. Saying "click Sign in" at a button named "Confirm code" does
 * nothing, and there is no visual symptom, so the defect was invisible to every screenshot and
 * every colour measurement. Styling does not fix it.
 *
 * WHY A PROPERTY TEST AND NOT FIVE UPDATED LITERALS. The five call sites' names were updated in
 * AccountSignIn, SignInMessages, CartCheckout, GetPage and PillButton, and those exact pins are
 * correct - they catch an accidental rename. But they only pin TODAY. A sixth pill, or a reworded
 * action, would satisfy every one of them and still ship a 2.5.3 failure. This file asserts the
 * invariant, so it keeps holding after the strings change.
 *
 * The repo already works this way on purpose: `test_payment_vocabulary_at_decision_points.py`
 * walks the AST to assert a property rather than a spelling, and `test_meta_version.py` records in
 * its own docstring that it pins the invariant rather than a number, because a number in a
 * document goes stale and a grep does not.
 *
 * HOW THE NAME IS COMPUTED, AND WHY NOT `dom-accessibility-api` DIRECTLY. The name comes from
 * Testing Library's own `*ByRole` name matching, which is the same `computeAccessibleName` every
 * other role query in this suite goes through - so this measures exactly what those queries and a
 * real AT client see. Importing `dom-accessibility-api` directly was tried first and `tsc` cannot
 * resolve its types through that package's `exports` map; using the role query avoids both the
 * import and a suppression, and is the more faithful measurement anyway.
 *
 * ON THE FUNCTION MATCHER. `name` is given a predicate here, which is deliberately NOT the
 * loosening that pinned queries must never do - a pin asserting one control's name stays an exact
 * string, and all five were updated to exact strings. "Contains" is the criterion itself in this
 * file, so a predicate is the only honest way to state it.
 */

/** Collapse whitespace so "Sign in Confirm code" and "Sign in  Confirm code" compare equal. */
const norm = ( value: string ): string => value.replace( /\s+/g, ' ' ).trim();

/**
 * Every prop shape in the codebase, so this covers the real call sites and not just a toy.
 * Taken from: /account/sign-in (x2 phases, idle and busy), /cart, and /get (x3).
 */
const CALL_SITES: Array<{
  where: string;
  role: 'button' | 'link';
  props: React.ComponentProps<typeof PillButton>;
}> = [
  { where: '/account/sign-in phone', role: 'button', props: { label: 'Sign in', action: 'Send code' } },
  { where: '/account/sign-in phone, busy', role: 'button', props: { label: 'Sign in', action: 'Sending…', busy: true } },
  { where: '/account/sign-in code', role: 'button', props: { label: 'Sign in', action: 'Confirm code' } },
  { where: '/account/sign-in code, busy', role: 'button', props: { label: 'Sign in', action: 'Checking…', busy: true } },
  { where: '/cart', role: 'button', props: { label: 'Checkout', action: 'Proceed' } },
  { where: '/cart, busy', role: 'button', props: { label: 'Checkout', action: 'Preparing…', busy: true } },
  { where: '/get mobile', role: 'button', props: { label: 'Collect', action: 'Send code' } },
  { where: '/get code', role: 'button', props: { label: 'Collect', action: 'Verify' } },
  { where: '/get pay', role: 'button', props: { label: 'Pay', action: 'Open WhatsApp' } },
  { where: 'anchor form', role: 'link', props: { as: 'a', href: '/cart/', label: 'Sign in', action: 'Continue' } },
];

describe( 'the accessible name contains the visible text, at every call site', () => {
  for ( const { where, role, props } of CALL_SITES ) {
    it( `satisfies 2.5.3 for ${ where }`, () => {
      const { container, unmount } = render( <PillButton { ...props } /> );
      const control = container.querySelector( '.pill' ) as HTMLElement;
      expect( control, 'no .pill control rendered' ).toBeTruthy();

      /*
       * COMPARED PER SEGMENT, NOT AGAINST textContent, AND THE DIFFERENCE IS REAL.
       *
       * `textContent` is the raw DOM concatenation with no separator - "Sign inContinue" - because
       * the segments are adjacent elements. The accessible-name algorithm joins element contents
       * with a space, giving "Sign in Continue", which is also how a sighted user reads it, since
       * the segments are separate flex items side by side. Asserting
       * name.contains(textContent) would fail on a correctly-named control: a bug in the
       * assertion, not in the component. jsdom computes no layout, so `innerText` cannot supply
       * the rendered spacing either.
       *
       * So each VISIBLE SEGMENT's own text must appear in the name, in reading order. That is
       * what 2.5.3 requires of a label made of more than one piece of text, and it holds however
       * the pieces are spaced.
       */
      const segments = [ ...control.querySelectorAll( 'span' ) ]
        .map( span => norm( span.textContent || '' ) )
        .filter( Boolean );
      expect( segments.length, 'expected the pill to render visible segment text' )
        .toBeGreaterThan( 0 );

      // Capture what Testing Library computes, for a diagnosable failure message.
      const computed: string[] = [];
      screen.queryAllByRole( role, {
        name: ( accessibleName: string ) => { computed.push( accessibleName ); return false; },
      } );

      const containsAllInOrder = ( accessibleName: string ): boolean => {
        const name = norm( accessibleName );
        let cursor = 0;
        for ( const segment of segments ) {
          const at = name.indexOf( segment, cursor );
          if ( at < 0 ) return false;
          cursor = at + segment.length;
        }
        return true;
      };

      const matches = screen.queryAllByRole( role, { name: containsAllInOrder } );
      expect( matches, `accessible name ${ JSON.stringify( computed ) } does not contain the `
        + `visible segments ${ JSON.stringify( segments ) } in order - WCAG 2.5.3 Label in Name` )
        .toHaveLength( 1 );

      // A non-empty name: a separate failure that "contains" alone would miss if the visible
      // text were also empty.
      expect( norm( computed[ 0 ] || '' ).length ).toBeGreaterThan( 0 );
      unmount();
    } );
  }

  it( 'hides neither segment from the accessibility tree', () => {
    // aria-hidden on a control's own visible label is what produced the mismatch, so its
    // absence is the structural part of the fix and is asserted directly.
    const { container } = render( <PillButton label="Sign in" action="Confirm code" /> );
    expect( container.querySelectorAll( '.pill [aria-hidden="true"]' ) ).toHaveLength( 0 );
  } );

  it( 'sets no aria-label, so the name cannot disagree with the screen', () => {
    const { container } = render( <PillButton label="Checkout" action="Proceed" /> );
    const control = container.querySelector( '.pill' ) as HTMLElement;
    expect( control.hasAttribute( 'aria-label' ) ).toBe( false );
  } );

  it( 'exposes no way to override the name, so 2.5.3 cannot be reopened by a caller', () => {
    // The `ariaLabel` prop was REMOVED rather than merely left unused: while it existed, any
    // caller could set a name that did not contain the visible text, which is exactly how this
    // shipped. Passing it must not take effect.
    render(
      // @ts-expect-error - the prop is deliberately gone from the public API.
      <PillButton label="Checkout" action="Proceed" ariaLabel="Proceed to checkout" />,
    );
    expect( screen.getByRole( 'button', { name: 'Checkout Proceed' } ) ).toBeTruthy();
    expect( screen.queryByRole( 'button', { name: 'Proceed to checkout' } ) ).toBeNull();
  } );

  it( 'keeps describedBy available, which adds description without replacing the name', () => {
    // The sanctioned way to attach extra context: aria-describedby is announced in addition to
    // the name, so it cannot create a Label in Name mismatch.
    const { container } = render(
      <PillButton label="Sign in" action="Send code" describedBy="si-error" />,
    );
    const control = container.querySelector( '.pill' ) as HTMLElement;
    expect( control.getAttribute( 'aria-describedby' ) ).toBe( 'si-error' );
    expect( screen.getByRole( 'button', { name: 'Sign in Send code' } ) ).toBeTruthy();
  } );
} );
