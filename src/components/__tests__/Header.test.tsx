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

  it( 'keeps Sign in and removes Contact and retired pages', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );
    expect( screen.getByRole( 'link', { name: 'Sign in' } ) ).toHaveAttribute( 'href', '/access' );

    // Contact is BACK, by owner request, and now points at a real local page - so the
    // assertion that it stays absent is retired rather than failing. It was there to
    // stop a deleted page creeping back into the menu, which is a decision the owner
    // has now reversed deliberately. Studio and Sustainability are still retired and
    // those guards stay.
    expect( screen.getByRole( 'link', { name: 'Contact' } ) ).toHaveAttribute( 'href', '/contact/' );
    expect( screen.queryByText( 'Studio' ) ).toBeNull();
    expect( screen.queryByText( 'Sustainability' ) ).toBeNull();
  } );

  it( 'moves Bharat Rx to Products and drops FAQ entirely', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );

    // FAQ has no entry point left anywhere: the local page was deleted earlier and
    // this row is now gone too.
    expect( screen.queryByRole( 'link', { name: 'FAQ' } ) ).toBeNull();

    // Bharat Rx is a product, not one of the Selfservice request actions. Asserted by
    // column position, because the label alone would pass wherever it sat.
    const products = screen.getByText( 'Products' ).closest( '.nav-group' );
    expect( products ).not.toBeNull();
    expect( products?.textContent ).toContain( 'Bharat Rx' );

    // Selfservice is found by TEXT, not by role=link. It used to be a link, because the
    // heading doubled as a link to the external landing page; that page is being retired
    // and the heading is now a plain group label, so getByRole('link') would throw here.
    const selfservice = screen.getByText( 'Selfservice' ).closest( '.nav-group' );
    expect( selfservice ).not.toBeNull();
    expect( selfservice?.textContent ).not.toContain( 'Bharat Rx' );

    // And it must NOT be a link any more - that is the actual requirement, so assert it
    // rather than leaving it implied by the lookup above happening to work.
    expect( screen.queryByRole( 'link', { name: 'Selfservice' } ) ).toBeNull();
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
  } );

  it( 'uses the approved public header dimensions and brand navigation colors', () => {
    const { container } = render( <Header /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    expect( css ).toContain( 'box-sizing:border-box;height:108px' );
    expect( css ).toContain( '@media(max-width:767px){.hdr-in{height:96px' );
    expect( css ).toContain( ".nav-trigger[aria-expanded='true']{background:rgba(209,244,112,.22)}" );

    // The dropdown control is a CSS-drawn chevron, not a text triangle. The old
    // literal glyph rendered nothing but a font character, so its shape and
    // weight varied by platform; two borders on a rotated box do not.
    const trigger = container.querySelector( 'button' );
    const arrow = container.querySelector( 'button span' );
    expect( trigger?.textContent ).toBe( '' );
    expect( container.textContent ).not.toContain( '▼' );
    expect( arrow ).not.toBeNull();
    expect( arrow?.getAttribute( 'aria-hidden' ) ).toBe( 'true' );

    // Drawn with two 2px WECARE.DIGITAL dark-green borders on a 7px border-box,
    // rotated 45deg. margin:0 defeats the global .nav-arrow{margin-left:auto}
    // in Layout.css, which would otherwise push it off centre.
    expect( css ).toContain( '.nav-arrow{width:7px;height:7px;box-sizing:border-box;margin:0' );
    expect( css ).toContain( 'border-right:2px solid #1a3a2a' );
    expect( css ).toContain( 'border-bottom:2px solid #1a3a2a' );
    expect( css ).toContain( 'transform:translateY(-2px) rotate(45deg)' );

    // Open state is an exact 180deg flip of the shape (45 -> 225), on the same
    // restrained .2s transition, still keyed off aria-expanded.
    expect( css ).toContain( ".nav-trigger[aria-expanded='true'] .nav-arrow{transform:translateY(2px) rotate(225deg)}" );
    expect( css ).toContain( 'transition:transform .2s' );
  } );
} );
