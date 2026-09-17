import React from 'react';
import { beforeAll, describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CrmPage from '../pages/crm';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );
vi.mock( 'next/script', () => ( { default: () => null } ) );

beforeAll( () => {
  class MockIntersectionObserver {
    observe () {}
    unobserve () {}
    disconnect () {}
  }
  vi.stubGlobal( 'IntersectionObserver', MockIntersectionObserver );
} );

describe( 'Grahak OS public page', () => {
  it( 'hosts the existing customer engagement marketing experience', () => {
    render( <CrmPage /> );
    expect( screen.getByText( /Reach more customers/i ) ).toBeInTheDocument();
    expect( screen.getByText( /Every touchpoint/i ) ).toBeInTheDocument();
    expect( screen.getByText( /Built for the AI era/i ) ).toBeInTheDocument();
    expect( screen.getByText( /Everything you need/i ) ).toBeInTheDocument();
  } );
} );
