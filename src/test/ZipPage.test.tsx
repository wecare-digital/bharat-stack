import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen, within } from '@testing-library/react';

import ZipPage from '../pages/zip';

/**
 * /zip — the request/delivery/pickup hub (Section 3).
 *
 * WHAT THIS GUARDS. The owner's heading and lead must be present, the real request routes must
 * resolve to the real existing pages, and the capabilities with NO backend (visit/pickup/delivery
 * tracking) must be clearly non-transacting: no href, not a button, and carrying aria-disabled so
 * nothing reads as a working booking control.
 *
 * next/head is a no-op in jsdom, so PageMeta renders nothing observable here; the assertions are
 * on the page body the shared band wraps.
 */
describe( 'Zip page', () => {
  it( 'renders the owner heading and lead through the shared band', () => {
    const { container } = render( <ZipPage /> );
    // One h1 from PageTopBand, carrying the mandated word.
    const h1s = container.querySelectorAll( 'h1' );
    expect( h1s ).toHaveLength( 1 );
    expect( h1s[ 0 ].textContent ).toBe( 'Zip' );
    // The mandated lead.
    expect( screen.getByText( 'Track it. Arrange it. Keep it moving.' ) ).toBeInTheDocument();
    // The shared band provides exactly one main landmark; the page does not add its own.
    expect( container.querySelectorAll( 'main' ) ).toHaveLength( 1 );
  } );

  it( 'links the real request actions to the pages that answer them', () => {
    render( <ZipPage /> );
    // Each of these is a real existing public route; the Zip hub must point straight at it.
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
    const { container } = render( <ZipPage /> );

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

    // The coming-soon affordances carry no href and are marked aria-disabled; there are no
    // buttons on the page at all (the only interactive elements are the real-route anchors).
    const soon = container.querySelectorAll( '.zip-soon[aria-disabled="true"]' );
    expect( soon.length ).toBe( 5 );
    soon.forEach( node => {
      expect( node.getAttribute( 'href' ) ).toBeNull();
      expect( node.tagName ).not.toBe( 'A' );
      expect( node.tagName ).not.toBe( 'BUTTON' );
    } );
    expect( container.querySelectorAll( 'button' ) ).toHaveLength( 0 );
  } );

  it( 'surfaces no transacting control or price', () => {
    const { container } = render( <ZipPage /> );
    const text = ( container.textContent || '' ).toLowerCase();
    // No priced/transacting furniture: Zip only signposts, it never sells.
    expect( text ).not.toContain( 'add to cart' );
    expect( text ).not.toContain( 'pay now' );
    expect( text ).not.toContain( '₹' );
  } );
} );

describe( 'Zip page is registered as a public route', () => {
  it( 'reuses PageMeta/PageTopBand rather than importing chrome', () => {
    const fs = require( 'node:fs' );
    const path = require( 'node:path' );
    const src = fs.readFileSync( path.join( process.cwd(), 'src/pages/zip.tsx' ), 'utf8' );
    expect( src ).toContain( "from '../components/PageTopBand'" );
    expect( src ).toContain( "from '../components/PageMeta'" );
    // Chrome is mounted centrally in _app.tsx; a page must never import it.
    expect( src ).not.toMatch( /components\/(Header|Footer|SupportWidget|Layout)'/ );
  } );
} );
