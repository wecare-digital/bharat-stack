import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';

import ShipmentsPage from '../pages/shipments';

/**
 * /shipments — the request/delivery/pickup hub (Section 3).
 *
 * THE PAGE WAS CALLED "ZIP"; the name is gone on owner instruction (2026-10-02) and this file was
 * renamed from ZipPage.test.tsx. The route is /shipments/, the badge carries the full house form
 * "Shipments by WECARE.DIGITAL", and no user-visible "Zip" survives. The assertions below are the
 * guard against the name creeping back, because the previous attempt renamed only the nav label
 * and left the route, the PUBLIC_PAGE_META `name` and the legal copy still saying "Zip".
 *
 * WHAT THIS GUARDS. The page matches the HOME PAGE: it renders the shared RotatingHero (the
 * reusable version of the home page's animated headline pill) and a scroll-reveal closing band
 * that uses the same opt-in .is-armed mechanism. These assertions therefore pin:
 *   - the page owns exactly one <h1> and one <main>, both provided by the hero (not a second of
 *     either, which htmlcheck's H1-MANY / MANY-MAIN guard against);
 *   - the full "Shipments by WECARE.DIGITAL" badge and the owner's lead are present;
 *   - the hero reuses RotatingHero rather than copying its markup, so the animation family cannot
 *     drift;
 *   - the real request routes still resolve to the real existing pages;
 *   - the capabilities with NO backend (visit / pickup / delivery tracking) are still clearly
 *     non-transacting: no href, not a button, carrying aria-disabled;
 *   - reduced-motion handling is still present (the hero's and the closing band's), so the
 *     animation can be turned off.
 *
 * next/head is a no-op in jsdom, so PageMeta renders nothing observable here; the assertions are
 * on the page body the hero wraps.
 */
describe( 'Shipments page', () => {
  it( 'owns a single h1 and a single main through the shared hero', () => {
    const { container } = render( <ShipmentsPage /> );
    // RotatingHero provides exactly one <h1> and one <main>; the page must not add its own of
    // either (htmlcheck guards H1-MANY and MANY-MAIN).
    expect( container.querySelectorAll( 'h1' ) ).toHaveLength( 1 );
    expect( container.querySelectorAll( 'main' ) ).toHaveLength( 1 );
  } );

  it( 'carries the Shipments identity and the owner lead on the animated hero', () => {
    const { container } = render( <ShipmentsPage /> );
    // The hero frame line, which with the rotating nouns forms the single h1.
    const h1 = container.querySelector( 'h1' );
    expect( h1?.textContent ).toContain( 'Everything about your' );
    // THE FULL HOUSE FORM in the brand badge above the headline. This asserts the whole string,
    // not a substring, because a bare "Shipments" badge is exactly the bug the owner reported.
    expect( screen.getByText( 'Shipments by WECARE.DIGITAL' ) ).toBeInTheDocument();
    // The retired name must never come back on the page.
    expect( container.textContent ).not.toMatch( /\bZip\b/i );
    // The mandated lead.
    expect( screen.getByText( 'Track it. Arrange it. Keep it moving.' ) ).toBeInTheDocument();
    // The rotation describes the page's own subject, not the home page's marketing audiences. The
    // screen-reader copy lists the words once; the animated copies are aria-hidden.
    const words = Array.from( container.querySelectorAll( '.rh-cyc-word' ) ).map( w => w.textContent );
    expect( words ).toEqual( [ 'order', 'request', 'delivery', 'pickup' ] );
  } );

  it( 'reuses the home-page hero component rather than importing chrome or copying markup', () => {
    const fs = require( 'node:fs' );
    const path = require( 'node:path' );
    const src = fs.readFileSync( path.join( process.cwd(), 'src/pages/shipments.tsx' ), 'utf8' );
    // The animated hero is the shared RotatingHero — the same component /shop/, /blog/ and the
    // product pages reuse — so the "animate as one family" guarantee holds.
    expect( src ).toContain( "from '../components/RotatingHero'" );
    expect( src ).toContain( "from '../components/PageMeta'" );
    // Chrome is mounted centrally in _app.tsx; a page must never import it.
    expect( src ).not.toMatch( /components\/(Header|Footer|SupportWidget|Layout)'/ );
    // Reduced-motion handling must survive on the page's own scroll-reveal band.
    expect( src ).toContain( 'prefers-reduced-motion: reduce' );
    expect( src ).toContain( 'prefers-reduced-motion:reduce' );
  } );

  it( 'links the real request actions to the pages that answer them', () => {
    render( <ShipmentsPage /> );
    // Each of these is a real existing public route; the Shipments hub must point straight at it.
    const expected: [ RegExp, string ][] = [
      [ /Track an order/i, '/orders/' ],
      [ /Track a request/i, '/orders/' ],
      [ /Amend a request/i, '/request-amendment/' ],
      [ /Send documents/i, '/drop-docs/' ],
      [ /Open your vault/i, '/vault/' ],
      [ /Leave a review/i, '/leave-review/' ],
    ];
    for ( const [ name, href ] of expected )
    {
      expect( screen.getByRole( 'link', { name } ) ).toHaveAttribute( 'href', href );
    }
  } );

  it( 'renders pickup / visit / delivery-tracking as non-transacting coming-soon items', () => {
    const { container } = render( <ShipmentsPage /> );

    // None of these has a backend in the repo, so none may be a working link or button.
    for ( const label of [
      'Book a visit', 'Prescription pickup', 'Book a pickup', 'Shipment pickup', 'Check delivery status',
    ] )
    {
      // Not a link.
      expect( screen.queryByRole( 'link', { name: new RegExp( label, 'i' ) } ) ).toBeNull();
      // Present on the page as text.
      expect( screen.getByText( label ) ).toBeInTheDocument();
    }

    // The coming-soon affordances carry no href and are marked aria-disabled; they are neither
    // links nor buttons, so nothing reads as a working booking control.
    const soon = container.querySelectorAll( '.ship-soon[aria-disabled="true"]' );
    expect( soon.length ).toBe( 5 );
    soon.forEach( node => {
      expect( node.getAttribute( 'href' ) ).toBeNull();
      expect( node.tagName ).not.toBe( 'A' );
      expect( node.tagName ).not.toBe( 'BUTTON' );
    } );
    // The only button-or-span inert controls are these five; no <button> is rendered anywhere.
    expect( container.querySelectorAll( 'button' ) ).toHaveLength( 0 );
  } );

  it( 'surfaces no transacting control or price', () => {
    const { container } = render( <ShipmentsPage /> );
    const text = ( container.textContent || '' ).toLowerCase();
    // No priced/transacting furniture: Shipments only signposts, it never sells.
    expect( text ).not.toContain( 'add to cart' );
    expect( text ).not.toContain( 'pay now' );
    expect( text ).not.toContain( '₹' );
  } );
} );
