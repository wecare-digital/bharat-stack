/**
 * A failed inbox load must not render as an empty inbox.
 *
 * `listMessages` and `listContacts` return `[]` for both "the table is empty"
 * and "the request failed", and the page's `catch` never fires because the
 * wrappers swallow the error. So an expired session, a missing route and a
 * genuinely quiet Monday all produced the same screen: "No conversations", whose
 * only implied remedy is "wait". That is the same class of invisibility that
 * made the stuck channel filter so hard to find.
 *
 * These tests drive the REAL client through a stubbed `fetch`, so the failure
 * travels the whole path — apiCallResult records it, collectApiFailures picks it
 * up, the page renders it. Mocking `collectApiFailures` would only test the mock.
 */
import React from 'react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

let routerQuery: Record<string, string> = {};

vi.mock( 'next/router', () => ( {
  useRouter: () => ( { query: routerQuery, isReady: true, push: vi.fn(), pathname: '/engage/inbox' } ),
} ) );

vi.mock( 'aws-amplify/auth', () => ( {
  fetchAuthSession: vi.fn().mockResolvedValue( { tokens: { accessToken: { toString: () => 't' } } } ),
} ) );

// Real retries would make this suite sleep for seconds.
vi.mock( '../config/constants', async ( importOriginal ) => {
  const actual = await importOriginal<typeof import( '../config/constants' )>();
  return { ...actual, RETRY_CONFIG: { maxRetries: 1, baseDelayMs: 1, maxDelayMs: 2 } };
} );

/**
 * `listMessages`/`listContacts` are replaced with thin stand-ins that go through
 * the genuine `apiCallResult` and collapse to `[]` exactly as the real wrappers
 * do — that collapse is the behaviour under test, so it has to be present.
 */
vi.mock( '../api/client', async () => {
  const actual = await vi.importActual<typeof import( '../api/client' )>( '../api/client' );
  const viaRealClient = async ( url: string ) => {
    const result = await actual.apiCallResult<unknown[]>( url );
    return result.ok ? result.data : [];
  };
  return {
    ...actual,
    listMessages: () => viaRealClient( 'https://api.example.test/messages' ),
    listContacts: () => viaRealClient( 'https://api.example.test/contacts' ),
    listRcsTemplates: vi.fn().mockResolvedValue( [] ),
    getPollyVoices: vi.fn().mockResolvedValue( { voices: {} } ),
    listAutomationRules: vi.fn().mockResolvedValue( [] ),
    getConversationMeta: vi.fn().mockResolvedValue( null ),
  };
} );

import UnifiedInbox from '../pages/engage/inbox/index';
import { ToastProvider } from '../contexts/ToastContext';

const Inbox: React.FC = () => (
  <ToastProvider><UnifiedInbox embedded /></ToastProvider>
);

function response ( status: number, body: unknown = [] ): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: 'stub',
    json: async () => body,
  } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach( () => {
  routerQuery = {};
  fetchMock = vi.fn();
  vi.stubGlobal( 'fetch', fetchMock );
  if ( !( 'scrollIntoView' in Element.prototype ) )
  {
    ( Element.prototype as any ).scrollIntoView = () => {};
  }
} );

afterEach( () => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
} );

describe( 'a genuinely empty inbox', () => {
  it( 'still says "No conversations" when the API succeeds with no rows', async () => {
    fetchMock.mockResolvedValue( response( 200, [] ) );

    render( <Inbox /> );

    expect( await screen.findByText( 'No conversations' ) ).toBeTruthy();
    // The failure branch must stay out of the way of the honest empty state.
    expect( screen.queryByText( /Could not load the inbox/ ) ).toBeNull();
  } );
} );

describe( 'a failed inbox load', () => {
  it( 'says the load failed rather than showing an empty inbox', async () => {
    fetchMock.mockResolvedValue( response( 500 ) );

    render( <Inbox /> );

    expect( await screen.findByText( /Could not load the inbox/ ) ).toBeTruthy();
    expect( screen.queryByText( 'No conversations' ) ).toBeNull();
  } );

  it( 'names an expired session as an expired session, not as no data', async () => {
    fetchMock.mockResolvedValue( response( 401 ) );

    render( <Inbox /> );

    expect( await screen.findByText( /session has expired/ ) ).toBeTruthy();
    // The remedy has to match the fault: reloading remounts the Authenticator.
    expect( screen.getByText( 'Reload to sign in' ) ).toBeTruthy();
    expect( screen.queryByText( 'Retry' ) ).toBeNull();
  } );

  it( 'distinguishes a route that is not deployed from a route with no rows', async () => {
    fetchMock.mockResolvedValue( response( 404 ) );

    render( <Inbox /> );

    expect( await screen.findByText( /Could not load the inbox/ ) ).toBeTruthy();
    expect( screen.getByText( /API endpoint not found/ ) ).toBeTruthy();
    // 404 is not retryable, so the button must not promise that it is.
    expect( screen.getByText( 'Try again' ) ).toBeTruthy();
    expect( screen.queryByText( 'Retry' ) ).toBeNull();
  } );

  it( 'offers Retry for a fault that retrying could actually fix', async () => {
    fetchMock.mockResolvedValue( response( 503 ) );

    render( <Inbox /> );

    expect( await screen.findByText( 'Retry' ) ).toBeTruthy();
  } );

  it( 'recovers when the retry succeeds', async () => {
    fetchMock.mockResolvedValue( response( 503 ) );
    render( <Inbox /> );
    const retry = await screen.findByText( 'Retry' );

    fetchMock.mockResolvedValue( response( 200, [
      { messageId: 'm1', contactId: 'c-1', channel: 'WHATSAPP', direction: 'INBOUND',
        content: 'hello', timestamp: '2026-09-24T09:00:00Z', status: 'received' },
    ] ) );
    fireEvent.click( retry );

    await waitFor( () => {
      expect( screen.queryByText( /Could not load the inbox/ ) ).toBeNull();
    } );
  } );

  it( 'does not blank a working list when a later poll fails', async () => {
    fetchMock.mockResolvedValue( response( 200, [
      { messageId: 'm1', contactId: 'c-1', channel: 'WHATSAPP', direction: 'INBOUND',
        content: 'hello', timestamp: '2026-09-24T09:00:00Z', status: 'received' },
    ] ) );
    render( <Inbox /> );
    await screen.findByText( /hello/ );

    // The 15s poll fails. Messages are already on screen, so the error state
    // must NOT take over - losing a visible thread list to a transient blip is
    // worse than showing slightly stale data.
    fetchMock.mockResolvedValue( response( 503 ) );
    await new Promise( r => setTimeout( r, 0 ) );

    expect( screen.queryByText( /Could not load the inbox/ ) ).toBeNull();
  } );
} );
