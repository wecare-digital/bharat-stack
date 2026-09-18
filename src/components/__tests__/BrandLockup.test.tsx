import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import BrandLockup from '../BrandLockup';

describe( 'BrandLockup', () => {
  it( 'renders the canonical Bharat Stack brand', () => {
    const { container } = render( <BrandLockup /> );
    expect( screen.getByText( 'Bharat' ) ).toBeInTheDocument();
    expect( screen.getByText( 'Stack' ) ).toBeInTheDocument();
    expect( container.querySelector( '.brand-lockup.full' ) ).toBeTruthy();
  } );

  it( 'uses the approved larger shared logo and wordmark scale', () => {
    const { container } = render( <BrandLockup /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );
    expect( css ).toContain( 'height:60px' );
    expect( css ).toContain( 'font-size:24px' );
    expect( css ).toContain( 'height:50px' );
    expect( css ).toContain( 'font-size:22px' );
  } );
} );
