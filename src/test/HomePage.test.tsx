import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import HomePage from '../pages/index';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

describe( 'Bharat Stack Home', () => {
  it( 'keeps the page body blank until the Home design is decided', () => {
    const { container } = render( <HomePage /> );
    expect( screen.queryByText( /Reach more customers/i ) ).toBeNull();
    expect( screen.queryByText( /Every touchpoint/i ) ).toBeNull();
    expect( screen.queryByText( /Built for the AI era/i ) ).toBeNull();
    expect( container.querySelector( 'main' ) ).toBeInTheDocument();
  } );

  it( 'keeps homepage content below the public header at every breakpoint', () => {
    const { container } = render( <HomePage /> );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    expect( css ).toContain( 'padding-top:108px' );
    expect( css ).toContain( 'padding-top:96px' );
  } );

  it( 'provides a centered responsive canvas with consistent section spacing', () => {
    const { container } = render( <HomePage /> );
    const layout = container.querySelector( 'main > .home-layout' );
    const css = Array.from( container.querySelectorAll( 'style' ) ).map( node => node.textContent || '' ).join( '\n' );

    expect( layout ).toBeInTheDocument();
    expect( css ).toContain( 'max-width:1300px' );
    expect( css ).toContain( 'padding:80px 24px 96px' );
    expect( css ).toContain( 'gap:96px' );
    expect( css ).toContain( 'padding:48px 16px 64px' );
    expect( css ).toContain( 'gap:64px' );
  } );
} );
