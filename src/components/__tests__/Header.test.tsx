import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import Header from '../Header';

const routerState = vi.hoisted( () => ( { pathname: '/' } ) );
vi.mock( 'next/router', () => ( { useRouter: () => routerState } ) );

describe( 'Header', () => {
  it( 'shows the shared WECARE.DIGITAL brand', () => {
    render( <Header /> );
    expect( screen.getByText( /WECARE/ ) ).toBeInTheDocument();
    expect( screen.getByText( 'DIGITAL' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'link', { name: /WECARE.DIGITAL home/i } ) ).toHaveAttribute( 'href', '/' );
  } );

  it( 'uses separate Home and Grahak OS routes', () => {
    routerState.pathname = '/';
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );
    expect( screen.getByRole( 'link', { name: 'Home' } ) ).toHaveAttribute( 'href', '/' );
    expect( screen.getByRole( 'link', { name: 'Home' } ) ).toHaveAttribute( 'aria-current', 'page' );
    expect( screen.getByRole( 'link', { name: 'Grahak OS' } ) ).toHaveAttribute( 'href', '/grahak-os/' );
    expect( screen.getByRole( 'link', { name: 'Grahak OS' } ) ).not.toHaveAttribute( 'aria-current' );
  } );

  it( 'marks Grahak OS active on its public route', () => {
    routerState.pathname = '/grahak-os';
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );
    expect( screen.getByRole( 'link', { name: 'Grahak OS' } ) ).toHaveAttribute( 'aria-current', 'page' );
  } );

  it( 'removes internal Sign in, and removes retired pages', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );

    // SIGN IN IS GONE from the public menu, on owner instruction. The old row pointed at
    // /access, the INTERNAL staff dashboard login (Cognito), which does not belong in
    // public navigation. A fresh customer login (WhatsApp OTP with SMS/email fallback)
    // will live on the /orders page instead. So there must be no "Sign in" link, and
    // no "Account" heading, anywhere in this menu.
    expect( screen.queryByRole( 'link', { name: 'Sign in' } ) ).toBeNull();
    expect( screen.queryByText( 'Account' ) ).toBeNull();

    // Contact now has its OWN heading ("Contact") with a single row labelled "Contact
    // us", both pointing at the real local /contact page. The link name is therefore
    // "Contact us"; assert that rather than the bare "Contact", which is now the group
    // heading, not a link. Studio and Sustainability are still retired and those guards stay.
    expect( screen.getByRole( 'link', { name: 'Contact us' } ) ).toHaveAttribute( 'href', '/contact/' );
    expect( screen.queryByText( 'Studio' ) ).toBeNull();
    expect( screen.queryByText( 'Sustainability' ) ).toBeNull();
  } );

  it( 'moves Bharat Rx to Products and drops FAQ entirely', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );

    // FAQ has no entry point left anywhere: the local page was deleted earlier and
    // this row is now gone too.
    expect( screen.queryByRole( 'link', { name: 'FAQ' } ) ).toBeNull();

    // Bharat Rx is a product, not one of the request actions. Asserted by
    // column position, because the label alone would pass wherever it sat.
    const products = screen.getByText( 'Products' ).closest( '.nav-group' );
    expect( products ).not.toBeNull();
    expect( products?.textContent ).toContain( 'Bharat Rx' );

    // The group is 'Requests', renamed from 'Selfservice' on 2026-09-27. Found by TEXT,
    // not by role=link: the heading used to double as a link to a landing page, that page
    // no longer exists at any address, and the heading is now a plain group label - so
    // getByRole('link') would throw here.
    const requests = screen.getByText( 'Requests' ).closest( '.nav-group' );
    expect( requests ).not.toBeNull();
    expect( requests?.textContent ).not.toContain( 'Bharat Rx' );

    // And it must NOT be a link - that is the actual requirement, so assert it
    // rather than leaving it implied by the lookup above happening to work.
    expect( screen.queryByRole( 'link', { name: 'Requests' } ) ).toBeNull();

    // The retired word must not come back anywhere in the menu. This is the guard for the
    // owner instruction, not a restatement of the rename: a new row or heading carrying
    // 'Selfservice' would name a destination that does not exist.
    expect( screen.queryByText( /Selfservice/i ) ).toBeNull();
  } );

  it( 'lists Terms and Privacy under a Legal Stuff heading', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );

    expect( screen.getByRole( 'link', { name: 'Terms' } ) ).toHaveAttribute( 'href', '/terms/' );

    // Privacy is linked now. It was deliberately unlinked while its text was a
    // placeholder, and the assertion here guarded that; the owner asked for it to be
    // listed once the real policy landed, so the guard is replaced rather than deleted.
    expect( screen.getByRole( 'link', { name: 'Privacy' } ) ).toHaveAttribute( 'href', '/privacy/' );

    // The heading matches the published document's own title.
    expect( screen.getByText( 'Legal Stuff' ) ).toBeInTheDocument();
    expect( screen.queryByText( /^Legal$/ ) ).toBeNull();

    // Legal Stuff now sits in the SAME column as "Refer & Earn" (the Work with us
    // column), not under the request actions where it used to be. Asserted by shared
    // column ancestor so a future reorder that splits them is caught.
    const legalCol = screen.getByText( 'Legal Stuff' ).closest( '.nav-col' );
    expect( legalCol ).not.toBeNull();
    expect( legalCol?.textContent ).toContain( 'Refer & Earn' );
    // And it is no longer beside the request actions. The group was renamed from
    // 'Selfservice' to 'Requests' on 2026-09-27; this looks it up by the new label.
    const requestsCol = screen.getByText( 'Requests' ).closest( '.nav-col' );
    expect( requestsCol?.textContent ).not.toContain( 'Legal Stuff' );
  } );

  it( 'uses the approved public header dimensions and brand navigation colors', () => {
    const { container } = render( <Header /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    expect( css ).toContain( 'box-sizing:border-box;height:108px' );
    expect( css ).toContain( '@media(max-width:767px){.hdr-in{height:96px' );

    /*
     * THE TRIGGER'S ACTIVE STATE INVERTS NOW. This asserted
     *   .nav-trigger[aria-expanded='true']{background:rgba(209,244,112,.22)}
     * and that value is exactly what was wrong with it. Over the white header that tint
     * composites to rgb(245,253,224), which measures 1.032:1 against the chip's own #f4f7ee - an
     * RGB move of 15 out of a possible 441. The test was pinning a state change that was not
     * perceptible, which is how it survived a report of "no hover effect".
     *
     * Lime cannot fix it either: lime is a LIGHT colour, so measured against #f4f7ee the solid
     * #d1f470 still only reaches 1.15:1. Only an inversion gives a luminance step - #1a3a2a is
     * 11.52:1 - so hover, focus-visible and expanded now share one dark fill with the chevron
     * flipping to lime at 10.04:1 on it.
     *
     * Asserted as one rule covering all three states, because the defect was partly that they
     * were separate declarations drifting apart.
     */
    expect( css ).toContain( ".nav-trigger:hover,.nav-trigger:focus-visible,.nav-trigger[aria-expanded='true']" );
    expect( css ).toContain( 'background:#1a3a2a;border-color:#1a3a2a' );

    /*
     * THE FOCUS RING IS TWO-TONE, AND BOTH STOPS ARE LOAD-BEARING.
     *
     * It was a single box-shadow at rgba(26,58,42,.2), which composites to rgb(200,209,199)
     * over the header and measures 1.44:1 against it - under the 3:1 WCAG 1.4.11 asks of a
     * focus indicator. The rule above also sets outline:none, so that faint shadow was the
     * entire ring.
     *
     * Opaque #1a3a2a on its own does not fix it, which is the part worth pinning: the rule
     * above fills this chip with #1a3a2a on focus, so a dark green ring drawn tight against
     * a dark green chip has no edge - it reads as a slightly larger chip, not as a ring.
     * The 2px white spacer is what gives it one, and the 3px of dark green outside measures
     * 12.48:1 against the white header.
     *
     * Do not collapse this to one stop in either direction.
     */
    expect( css ).toContain( '.nav-trigger:focus-visible{box-shadow:0 0 0 2px #fff,0 0 0 5px #1a3a2a}' );
    // Comments stripped before the negative check: the rule above documents the value it
    // replaced, and a substring search cannot tell a citation from a declaration. Banning
    // the string outright would mean deleting the measurement that justifies the fix.
    expect( css.replace( /\/\*[\s\S]*?\*\//g, '' ) ).not.toContain( 'rgba(26,58,42,.2)' );
    // And the chevron inverts with it, or it would be dark-on-dark.
    expect( css ).toContain( 'border-right-color:#d1f470;border-bottom-color:#d1f470;opacity:1' );

    // The dropdown control is a CSS-drawn chevron, not a text triangle. The old
    // literal glyph rendered nothing but a font character, so its shape and
    // weight varied by platform; two borders on a rotated box do not.
    const trigger = container.querySelector( 'button' );
    const arrow = container.querySelector( 'button span' );
    expect( trigger?.textContent ).toBe( '' );
    expect( container.textContent ).not.toContain( '▼' );
    expect( arrow ).not.toBeNull();
    expect( arrow?.getAttribute( 'aria-hidden' ) ).toBe( 'true' );

    // Drawn with two 2.5px WECARE.DIGITAL dark-green borders on an 8px border-box,
    // rotated 45deg, at .85 opacity. margin:0 defeats the global
    // .nav-arrow{margin-left:auto} in Layout.css, which would otherwise push it off
    // centre. Sizes were bumped from 7px/2px to 8px/2.5px so the chevron reads as a
    // solid arrow rather than a thin hairline that vanished on some displays.
    expect( css ).toContain( '.nav-arrow{width:8px;height:8px;box-sizing:border-box;margin:0' );
    expect( css ).toContain( 'border-right:2.5px solid #1a3a2a' );
    expect( css ).toContain( 'border-bottom:2.5px solid #1a3a2a' );
    expect( css ).toContain( 'transform:translateY(-2px) rotate(45deg)' );

    // Open state is an exact 180deg flip of the shape (45 -> 225), on the same
    // restrained .2s transition, still keyed off aria-expanded.
    expect( css ).toContain( ".nav-trigger[aria-expanded='true'] .nav-arrow{transform:translateY(2px) rotate(225deg)}" );
    expect( css ).toContain( 'transition:transform .2s' );
  } );
} );
