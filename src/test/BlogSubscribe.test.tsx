import { readFileSync } from 'node:fs';
import { join } from 'node:path';

import React from 'react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';

import BlogSubscribe from '../components/BlogSubscribe';

afterEach( () => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
} );

describe( 'BlogSubscribe', () => {
  it( 'renders the four requested fields and keeps Subscribe locked until both verifications', () => {
    render( <BlogSubscribe /> );

    expect( screen.getByLabelText( 'First name' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Last name' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Country code' ) ).toBeInTheDocument();
    expect( screen.getByLabelText( 'Email' ) ).toBeInTheDocument();

    const subscribe = screen.getByRole( 'button', { name: 'Subscribe' } ) as HTMLButtonElement;
    expect( subscribe.disabled ).toBe( true );
  } );

  it( 'requests the WhatsApp OTP through the narrow public blog endpoint', async () => {
    const fetchMock = vi.fn().mockResolvedValue( {
      ok: true,
      json: async () => ( { status: 'sent', expiresInSeconds: 300 } ),
    } );
    vi.stubGlobal( 'fetch', fetchMock );
    render( <BlogSubscribe /> );

    fireEvent.change( screen.getByPlaceholderText( '10-digit WhatsApp number' ), {
      target: { value: '9330994400' },
    } );
    const sendButtons = screen.getAllByRole( 'button', { name: 'Send code' } );
    fireEvent.click( sendButtons[ 0 ] );

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 1 ) );
    const [ url, init ] = fetchMock.mock.calls[ 0 ];
    expect( String( url ) ).toContain( '/blog/subscribe' );
    expect( JSON.parse( ( init as RequestInit ).body as string ) ).toMatchObject( {
      action: 'phone_request',
      phone: '+919330994400',
    } );
    expect( screen.getByLabelText( 'WhatsApp verification code' ) ).toBeInTheDocument();
  } );

  it( 'uses the shared PhoneField and PillButton and keeps the mobile row horizontally scrollable', () => {
    const source = readFileSync(
      join( __dirname, '..', 'components', 'BlogSubscribe.tsx' ), 'utf8',
    );
    expect( source ).toContain( "import PhoneField from './PhoneField'" );
    expect( source ).toContain( "import PillButton from './PillButton'" );
    expect( source ).toContain( 'flex-wrap:nowrap;overflow-x:auto' );
    expect( source ).toContain( 'scroll-snap-type:x proximity' );
  } );

  it( 'states that both verified channels are for subscribed blog updates', () => {
    render( <BlogSubscribe /> );
    expect( screen.getByText(
      /We’ll use both only for WECARE\.DIGITAL blog updates you subscribe to\./
    ) ).toBeInTheDocument();
  } );
} );
