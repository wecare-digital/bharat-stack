import React from 'react';
import { describe, expect, it } from 'vitest';
import { fireEvent, render, screen } from '@testing-library/react';
import Header from '../Header';

describe( 'Header', () => {
  it( 'shows the shared Bharat Stack brand', () => {
    render( <Header /> );
    expect( screen.getByText( 'Bharat' ) ).toBeInTheDocument();
    expect( screen.getByText( 'Stack' ) ).toBeInTheDocument();
    expect( screen.getByRole( 'link', { name: /Bharat Stack home/i } ) ).toHaveAttribute( 'href', '/' );
  } );

  it( 'uses the approved public navigation', () => {
    render( <Header /> );
    fireEvent.click( screen.getByRole( 'button', { name: 'Open navigation' } ) );
    expect( screen.getByRole( 'link', { name: 'Home' } ) ).toHaveAttribute( 'href', '/' );
    expect( screen.getByRole( 'link', { name: 'Grahak OS' } ) ).toHaveAttribute( 'href', '/crm' );
    expect( screen.getByRole( 'link', { name: 'Sign in' } ) ).toHaveAttribute( 'href', '/access' );
    expect( screen.getByRole( 'link', { name: 'Contact' } ) ).toHaveAttribute( 'href', 'https://www.wecare.digital/contact' );
    expect( screen.queryByText( 'Studio' ) ).toBeNull();
    expect( screen.queryByText( 'Sustainability' ) ).toBeNull();
  } );

  it( 'ships the larger responsive marketing type scale', () => {
    const { container } = render( <Header /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );
    expect( css ).toContain( 'clamp(38px,5.3vw,68px)' );
    expect( css ).toContain( 'clamp(18px,1.7vw,22px)' );
    expect( css ).toContain( 'clamp(32px,4vw,52px)' );
  } );
} );
