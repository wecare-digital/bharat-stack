import React from 'react';
import { describe, expect, it, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import CrmPage from '../pages/crm';

vi.mock( 'next/head', () => ( { default: ( { children }: { children: React.ReactNode } ) => <>{ children }</> } ) );

describe( 'legacy CRM public route', () => {
  it( 'redirects visitors to the Grahak OS public route', () => {
    render( <CrmPage /> );
    expect( screen.queryByText( /Reach more customers/i ) ).toBeNull();
    expect( document.querySelector( 'meta[http-equiv="refresh"]' ) ).toHaveAttribute( 'content', '0; url=/grahak-os/' );
    expect( screen.getByRole( 'link', { name: /Continue to Grahak OS/i } ) ).toHaveAttribute( 'href', '/grahak-os/' );
  } );
} );
