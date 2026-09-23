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

  it( 'uses the approved larger shared logo and wordmark scale', () => {
    const { container } = render( <BrandLockup /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    // Sized up on request: 60 -> 68px logo and 24 -> 26px type on desktop,
    // 50 -> 60px and 22 -> 24px on mobile.
    //
    // 68px is not a round number by accident - it is the ceiling. .hdr-in is
    // height:108px with 18px padding and box-sizing:border-box, so the content box is
    // exactly 72px; a 72px logo touches both edges. Mobile is 96px with 14px padding,
    // a 68px box, so 60px there. Both header heights are pinned by Header.test.tsx,
    // so the logo is what gives, not the header.
    expect( css ).toContain( 'height:68px' );
    expect( css ).toContain( 'font-size:26px' );
    expect( css ).toContain( 'height:60px' );
    expect( css ).toContain( 'font-size:24px' );
  } );
} );
