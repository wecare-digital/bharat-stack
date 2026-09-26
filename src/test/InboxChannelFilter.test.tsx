/**
 * The unified inbox must not get stuck on a channel filter.
 *
 * The bug this pins, in full, because the symptom was "the inbox stopped showing
 * messages" and the cause was three lines away from anything that looked related:
 *
 * All six sidebar Inbox entries point at the SAME route, `/workspace/inbox`, differing only
 * by query string. Next therefore keeps the component mounted across them, so React
 * state survives the navigation. The first version of the `?channel=` effect only ever
 * *set* the filter:
 *
 *     if ( q && q in CHANNEL ) setChannelFilter( q );
 *
 * so going `?channel=email` -> "All channels" left `channelFilter` on `email`. The
 * live table has ZERO `channel='email'` rows, so the page that promises every channel
 * rendered "No conversations" while the API was returning 244 messages every 15
 * seconds. Nothing errored, nothing logged, and the fetch was provably fine.
 *
 * `dm/logs` never had this because it derives its channel with `useMemo`. The inbox
 * cannot do that - its selector has to stay user-changeable - so it needs the explicit
 * reset, and that is what these tests hold in place.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import fs from 'node:fs';
import path from 'node:path';

let routerQuery: Record<string, string> = {};
let routerReady = true;

vi.mock( 'next/router', () => ( {
  useRouter: () => ( {
    query: routerQuery,
    isReady: routerReady,
    push: vi.fn(),
    pathname: '/workspace/inbox',
  } ),
} ) );

vi.mock( 'aws-amplify/auth', () => ( {
  fetchAuthSession: vi.fn().mockResolvedValue( { tokens: { accessToken: { toString: () => 't' } } } ),
} ) );

const listMessages = vi.fn();
const listContacts = vi.fn();

vi.mock( '../api/client', async () => {
  const actual = await vi.importActual<any>( '../api/client' );
  return {
    ...actual,
    listMessages: ( ...a: unknown[] ) => listMessages( ...a ),
    listContacts: ( ...a: unknown[] ) => listContacts( ...a ),
    listRcsTemplates: vi.fn().mockResolvedValue( [] ),
    getPollyVoices: vi.fn().mockResolvedValue( { voices: {} } ),
    listAutomationRules: vi.fn().mockResolvedValue( [] ),
    getConversationMeta: vi.fn().mockResolvedValue( null ),
  };
} );

import UnifiedInbox from '../pages/workspace/inbox/index';
import { ToastProvider } from '../contexts/ToastContext';

const SRC = fs.readFileSync(
  path.resolve( __dirname, '../pages/workspace/inbox/index.tsx' ), 'utf8' );

/** The inbox calls useToastContext, so it needs the provider to mount at all. */
const Inbox: React.FC<{ channel?: string }> = ( { channel } ) => (
  <ToastProvider>
    <UnifiedInbox embedded channel={ channel } />
  </ToastProvider>
);

/** Mirrors what the API actually returns: UPPERCASE channel, camelCase fields. */
function msg( over: Partial<Record<string, unknown>> = {} ) {
  return {
    id: 'm1', messageId: 'm1', contactId: 'c-1', channel: 'WHATSAPP',
    direction: 'INBOUND', content: 'hello from whatsapp',
    timestamp: new Date( '2026-09-24T09:00:00Z' ).toISOString(),
    status: 'received', senderPhone: '+918100640044', ...over,
  };
}

const WHATSAPP = msg();
const RCS = msg( { id: 'm2', messageId: 'm2', contactId: 'c-2', channel: 'RCS', content: 'hello from rcs' } );

beforeEach( () => {
  routerQuery = {};
  routerReady = true;
  listMessages.mockResolvedValue( [ WHATSAPP, RCS ] );
  listContacts.mockResolvedValue( [
    { contactId: 'c-1', name: 'Asha' }, { contactId: 'c-2', name: 'Ravi' },
  ] );
  if ( !( 'scrollIntoView' in Element.prototype ) ) {
    ( Element.prototype as any ).scrollIntoView = () => {};
  }
} );

afterEach( () => {
  vi.clearAllTimers();
} );

describe( 'the inbox shows messages', () => {
  it( 'renders conversations with no channel in the URL', async () => {
    render( <Inbox /> );
    expect( await screen.findByText( 'Asha' ) ).toBeTruthy();
    expect( screen.getByText( 'Ravi' ) ).toBeTruthy();
  } );

  it( 'fetches ALL channels and filters client-side, never per-channel', async () => {
    render( <Inbox /> );
    await screen.findByText( 'Asha' );
    // One fetch for everything is what lets the channel badges on a conversation
    // show every channel it has touched. A per-channel fetch could not.
    expect( listMessages ).toHaveBeenCalledWith( undefined, 'ALL', 2000 );
  } );

  it( 'matches the UPPERCASE channel the API returns against its lowercase map', async () => {
    routerQuery = { channel: 'whatsapp' };
    render( <Inbox /> );
    expect( await screen.findByText( 'Asha' ) ).toBeTruthy();
    // Ravi is RCS, so he must be filtered out — proving the comparison works in
    // both directions rather than passing everything through.
    expect( screen.queryByText( 'Ravi' ) ).toBeNull();
  } );
} );

describe( 'the channel filter resets when the URL drops it', () => {
  it( 'narrows to the channel named in the query', async () => {
    routerQuery = { channel: 'rcs' };
    render( <Inbox /> );
    expect( await screen.findByText( 'Ravi' ) ).toBeTruthy();
    expect( screen.queryByText( 'Asha' ) ).toBeNull();
  } );

  it( 'does NOT stay stuck on a channel after the query is removed', async () => {
    // The regression, reproduced. Same component instance, query cleared — which is
    // exactly what clicking "All channels" after "Email" does, because both are
    // `/workspace/inbox`.
    routerQuery = { channel: 'rcs' };
    const view = render( <Inbox /> );
    expect( await screen.findByText( 'Ravi' ) ).toBeTruthy();
    expect( screen.queryByText( 'Asha' ) ).toBeNull();

    routerQuery = {};
    view.rerender( <Inbox /> );

    await waitFor( () => expect( screen.getByText( 'Asha' ) ).toBeTruthy() );
    expect( screen.getByText( 'Ravi' ) ).toBeTruthy();
  } );

  it( 'an empty channel does not permanently hide everything else', async () => {
    // `email` has zero rows in the live table, so this is the exact path the owner
    // hit: pick Email, see nothing, go back to All channels, still see nothing.
    routerQuery = { channel: 'email' };
    const view = render( <Inbox /> );
    await waitFor( () => expect( screen.queryByText( 'Asha' ) ).toBeNull() );

    routerQuery = {};
    view.rerender( <Inbox /> );
    await waitFor( () => expect( screen.getByText( 'Asha' ) ).toBeTruthy() );
  } );

  it( 'switches straight from one channel to another', async () => {
    routerQuery = { channel: 'whatsapp' };
    const view = render( <Inbox /> );
    expect( await screen.findByText( 'Asha' ) ).toBeTruthy();

    routerQuery = { channel: 'rcs' };
    view.rerender( <Inbox /> );
    await waitFor( () => expect( screen.getByText( 'Ravi' ) ).toBeTruthy() );
    expect( screen.queryByText( 'Asha' ) ).toBeNull();
  } );

  it( 'ignores an unknown channel rather than hiding everything', async () => {
    routerQuery = { channel: 'telepathy' };
    render( <Inbox /> );
    // Falls back to ALL. Hiding every conversation because a URL was mistyped is the
    // worst available response.
    expect( await screen.findByText( 'Asha' ) ).toBeTruthy();
    expect( screen.getByText( 'Ravi' ) ).toBeTruthy();
  } );

  it( 'does not reset a deep-linked channel before the router is ready', async () => {
    // Static export: `router.query` is empty until hydration. Resetting on that pass
    // would flash ALL over a deep link to ?channel=rcs.
    routerReady = false;
    routerQuery = {};
    const view = render( <Inbox channel="rcs" /> );
    expect( await screen.findByText( 'Ravi' ) ).toBeTruthy();
    expect( screen.queryByText( 'Asha' ) ).toBeNull();

    routerReady = true;
    view.rerender( <Inbox channel="rcs" /> );
    await waitFor( () => expect( screen.getByText( 'Ravi' ) ).toBeTruthy() );
    expect( screen.queryByText( 'Asha' ) ).toBeNull();
  } );
} );

describe( 'a hub preset outranks the URL', () => {
  it( 'keeps the prop channel even when the query says something else', async () => {
    // The RCS and Email hubs embed this with their own channel. A stale URL must not
    // repurpose the Email hub into an RCS view.
    routerQuery = { channel: 'whatsapp' };
    render( <Inbox channel="rcs" /> );
    expect( await screen.findByText( 'Ravi' ) ).toBeTruthy();
    expect( screen.queryByText( 'Asha' ) ).toBeNull();
  } );

  it( 'keeps the prop channel when the query is cleared', async () => {
    routerQuery = { channel: 'whatsapp' };
    const view = render( <Inbox channel="rcs" /> );
    expect( await screen.findByText( 'Ravi' ) ).toBeTruthy();

    routerQuery = {};
    view.rerender( <Inbox channel="rcs" /> );
    await waitFor( () => expect( screen.getByText( 'Ravi' ) ).toBeTruthy() );
    expect( screen.queryByText( 'Asha' ) ).toBeNull();
  } );
} );

describe( 'the empty state explains itself', () => {
  it( 'names the channel and offers the way back', async () => {
    routerQuery = { channel: 'email' };
    render( <Inbox /> );

    expect( await screen.findByText( /No Email conversations/i ) ).toBeTruthy();
    // The number is the point: it distinguishes "this channel is quiet" from "the
    // load failed", which is the ambiguity that made a working inbox look broken.
    expect( screen.getByText( /2 messages on other channels/i ) ).toBeTruthy();

    fireEvent.click( screen.getByRole( 'button', { name: /Show all channels/i } ) );
    await waitFor( () => expect( screen.getByText( 'Asha' ) ).toBeTruthy() );
  } );

  it( 'says plainly that there is nothing at all when ALL is empty', async () => {
    listMessages.mockResolvedValue( [] );
    render( <Inbox /> );
    expect( await screen.findByText( 'No conversations' ) ).toBeTruthy();
    // No "on other channels" claim when there are none.
    expect( screen.queryByText( /on other channels/i ) ).toBeNull();
  } );
} );

describe( 'the source keeps the fix', () => {
  it( 'sets the filter on every query change, not only when a channel is present', () => {
    const code = SRC
      .replace( /\/\*[\s\S]*?\*\//g, '' )
      .replace( /^\s*\/\/.*$/gm, '' );
    // The one-way form is what broke it. Comments are stripped first because the
    // block explaining the bug contains the banned pattern verbatim.
    expect( code ).not.toMatch( /if\s*\(\s*q\s*&&\s*q\s+in\s+CHANNEL\s*\)\s*setChannelFilter/ );
    expect( code ).toMatch( /setChannelFilter\(\s*q\s*&&\s*q\s+in\s+CHANNEL\s*\?\s*q\s*:\s*'ALL'\s*\)/ );
  } );

  it( 'waits for the router before resetting', () => {
    expect( SRC ).toContain( 'router.isReady' );
  } );
} );
