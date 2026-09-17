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
} );
