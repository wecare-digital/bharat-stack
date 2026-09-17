import React from 'react';
import { describe, expect, it } from 'vitest';
import { render, screen } from '@testing-library/react';
import Header from '../Header';

describe( 'Header', () => {
  it( 'keeps the existing logo-only header by default', () => {
    render( <Header /> );
    expect( screen.queryByText( 'Bharat' ) ).toBeNull();
    expect( screen.queryByText( 'Stack' ) ).toBeNull();
    expect( screen.getByAltText( 'WECARE.DIGITAL' ) ).toBeInTheDocument();
  } );

  it( 'shows the Bharat Stack wordmark only for Home', () => {
    render( <Header homeBrand /> );
    expect( screen.getByText( 'Bharat' ) ).toBeInTheDocument();
    expect( screen.getByText( 'Stack' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'link', { name: /Bharat Stack home/i } ) ).toHaveAttribute( 'href', '/' );
  } );
} );
