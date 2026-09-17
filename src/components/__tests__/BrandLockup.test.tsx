import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import BrandLockup from '../BrandLockup';

describe( 'BrandLockup', () => {
  it( 'renders the canonical Home Bharat Stack brand', () => {
    const { container } = render( <BrandLockup /> );
    expect( screen.getByText( 'Bharat' ) ).toBeInTheDocument();
    expect( screen.getByText( 'Stack' ) ).toBeInTheDocument();
    expect( container.querySelector( '.brand-lockup.full' ) ).toBeTruthy();
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );
    expect( css ).toContain( 'height:46px' );
    expect( css ).toContain( 'font-size:19px' );
    expect( css ).toContain( 'font-weight:800' );
  } );
} );
