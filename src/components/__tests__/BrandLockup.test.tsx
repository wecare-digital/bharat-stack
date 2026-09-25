import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import BrandLockup from '../BrandLockup';

describe( 'BrandLockup', () => {
  it( 'renders the canonical WECARE.DIGITAL brand', () => {
    const { container } = render( <BrandLockup /> );
    expect( screen.getByText( /WECARE/ ) ).toBeInTheDocument();
    expect( screen.getByText( 'DIGITAL' ) ).toBeInTheDocument();
    expect( container.querySelector( '.brand-lockup.full' ) ).toBeTruthy();
  } );

  it( 'uses the approved shared logo and wordmark scale, stepping down on mobile', () => {
    const { container } = render( <BrandLockup /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    // Sized DOWN on request: 68 -> 60px logo and 26 -> 23px type on desktop, with mobile
    // scaled by the same ~0.88 to 54px/21px.
    //
    // The header still bounds the desktop value: .hdr-in is height:108px with 18px
    // padding and box-sizing:border-box, so the content box is exactly 72px and 68px was
    // the old ceiling; 60px simply sits further inside it. Mobile is 96px with 14px
    // padding, a 68px box, so 54px clears comfortably. Both header heights are pinned by
    // Header.test.tsx, so the logo is what gives, not the header.
    expect( css ).toContain( 'height:60px' );
    expect( css ).toContain( 'font-size:23px' );
    expect( css ).toContain( 'height:54px' );
    expect( css ).toContain( 'font-size:21px' );

    // THE LADDER MUST NOT INVERT. An earlier pass shrank desktop to 60px/23px and left
    // mobile at 60px/24px, which made the phone logo identical to the desktop one and the
    // phone wordmark LARGER than the desktop wordmark. Assert the old mobile values are
    // gone so that cannot silently come back.
    expect( css ).not.toContain( 'font-size:24px' );
    expect( css ).not.toContain( 'height:68px' );
  } );
} );
