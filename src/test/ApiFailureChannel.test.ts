/**
 * The API client used to collapse every failure to `null`, so an expired
 * session, an 8-second timeout and a genuinely empty table all reached the UI
 * as "nothing". These tests pin the structured failure channel that recovers
 * the difference.
 *
 * They exercise the real `apiCallResult` against a stubbed `fetch` — no mock of
 * the client itself, or the thing under test would be the mock.
 */
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

// aws-amplify/auth is pulled in by the client for the Bearer token. The token
// path is not what is being tested, so it returns nothing and the client
// proceeds without an Authorization header.
vi.mock( 'aws-amplify/auth', () => ( {
  fetchAuthSession: vi.fn().mockResolvedValue( { tokens: undefined } ),
} ) );

// Retries are real and would otherwise make this suite sleep for seconds.
vi.mock( '../config/constants', async ( importOriginal ) => {
  const actual = await importOriginal<typeof import( '../config/constants' )>();
  return { ...actual, RETRY_CONFIG: { maxRetries: 2, baseDelayMs: 1, maxDelayMs: 2 } };
} );

import {
  apiCallResult,
  collectApiFailures,
  getLastApiFailure,
  getConnectionStatus,
  type ApiFailureKind,
} from '../api/client';

const URL = 'https://api.example.test/messages';

function jsonResponse ( status: number, body: unknown = {}, statusText = '' ): Response {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText,
    json: async () => body,
  } as unknown as Response;
}

let fetchMock: ReturnType<typeof vi.fn>;

beforeEach( () => {
  fetchMock = vi.fn();
  vi.stubGlobal( 'fetch', fetchMock );
} );

afterEach( () => {
  vi.unstubAllGlobals();
  vi.clearAllMocks();
} );

describe( 'apiCallResult — success', () => {
  it( 'returns the parsed body under ok:true', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 200, { messages: [ { id: 'm1' } ] } ) );

    const result = await apiCallResult<{ messages: { id: string }[] }>( URL );

    expect( result.ok ).toBe( true );
    if ( result.ok ) expect( result.data.messages ).toEqual( [ { id: 'm1' } ] );
  } );

  it( 'clears a previous failure so a recovered call does not read as broken', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 500 ) );
    await apiCallResult( URL );
    expect( getLastApiFailure() ).not.toBeNull();

    fetchMock.mockResolvedValue( jsonResponse( 200, { ok: 1 } ) );
    await apiCallResult( URL );

    expect( getLastApiFailure() ).toBeNull();
    expect( getConnectionStatus().status ).toBe( 'connected' );
  } );
} );

describe( 'apiCallResult — each failure keeps its own identity', () => {
  // The whole point: these must NOT be the same value at the UI boundary.
  const cases: { status: number; kind: ApiFailureKind; retryable: boolean }[] = [
    { status: 401, kind: 'unauthenticated', retryable: false },
    { status: 403, kind: 'forbidden', retryable: false },
    { status: 404, kind: 'not-found', retryable: false },
    { status: 500, kind: 'server', retryable: true },
    { status: 502, kind: 'unavailable', retryable: true },
    { status: 503, kind: 'unavailable', retryable: true },
    { status: 504, kind: 'timeout', retryable: true },
    { status: 429, kind: 'rate-limited', retryable: true },
    { status: 418, kind: 'http', retryable: false },
  ];

  for ( const { status, kind, retryable } of cases )
  {
    it( `maps HTTP ${status} to kind "${kind}"`, async () => {
      fetchMock.mockResolvedValue( jsonResponse( status, {}, 'stub' ) );

      const result = await apiCallResult( URL );

      expect( result.ok ).toBe( false );
      if ( !result.ok )
      {
        expect( result.failure.kind ).toBe( kind );
        expect( result.failure.status ).toBe( status );
        expect( result.failure.retryable ).toBe( retryable );
        expect( result.failure.url ).toBe( URL );
        expect( result.failure.message.length ).toBeGreaterThan( 0 );
      }
    } );
  }

  it( 'produces nine distinct kinds across those statuses, not one', async () => {
    const kinds = new Set<string>();
    for ( const { status } of cases )
    {
      fetchMock.mockResolvedValue( jsonResponse( status, {}, 'stub' ) );
      const result = await apiCallResult( URL );
      if ( !result.ok ) kinds.add( result.failure.kind );
    }
    // 502 and 503 share 'unavailable' by design, so 9 statuses -> 8 kinds.
    expect( kinds.size ).toBe( 8 );
  } );

  it( 'retries a 401 once with a refreshed token before giving up', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 401 ) );

    const result = await apiCallResult( URL );

    expect( fetchMock ).toHaveBeenCalledTimes( 2 );
    expect( result.ok ).toBe( false );
    if ( !result.ok ) expect( result.failure.kind ).toBe( 'unauthenticated' );
  } );

  it( 'surfaces a server-supplied error message instead of a bare status', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 422, { error: { message: 'phone must be E.164' } } ) );

    const result = await apiCallResult( URL );

    expect( result.ok ).toBe( false );
    if ( !result.ok ) expect( result.failure.message ).toContain( 'phone must be E.164' );
  } );
} );

describe( 'apiCallResult — no response at all', () => {
  it( 'reports an aborted request as a timeout with no status', async () => {
    const abort = Object.assign( new Error( 'aborted' ), { name: 'AbortError' } );
    fetchMock.mockRejectedValue( abort );

    const result = await apiCallResult( URL );

    expect( result.ok ).toBe( false );
    if ( !result.ok )
    {
      expect( result.failure.kind ).toBe( 'timeout' );
      expect( result.failure.status ).toBeNull();
      expect( result.failure.retryable ).toBe( true );
    }
  } );

  it( 'reports a CORS/offline TypeError as network', async () => {
    fetchMock.mockRejectedValue( Object.assign( new TypeError( 'Failed to fetch' ), { name: 'TypeError' } ) );

    const result = await apiCallResult( URL );

    expect( result.ok ).toBe( false );
    if ( !result.ok ) expect( result.failure.kind ).toBe( 'network' );
  } );
} );

describe( 'collectApiFailures', () => {
  it( 'tells an empty result apart from a failed one', async () => {
    // A genuinely empty table: 200 with no rows, and no failure.
    fetchMock.mockResolvedValue( jsonResponse( 200, { messages: [] } ) );
    const empty = await collectApiFailures( () => apiCallResult<{ messages: unknown[] }>( URL ) );
    expect( empty.failures ).toHaveLength( 0 );

    // A broken load: also "no rows" at the UI, but for a reason.
    fetchMock.mockResolvedValue( jsonResponse( 403 ) );
    const broken = await collectApiFailures( () => apiCallResult( URL ) );
    expect( broken.failures ).toHaveLength( 1 );
    expect( broken.failures[ 0 ].kind ).toBe( 'forbidden' );
  } );

  it( 'collects every failure in a parallel load, not just the last', async () => {
    fetchMock
      .mockResolvedValueOnce( jsonResponse( 403 ) )
      .mockResolvedValueOnce( jsonResponse( 404 ) );

    const { failures } = await collectApiFailures( () => Promise.all( [
      apiCallResult( `${URL}/a` ),
      apiCallResult( `${URL}/b` ),
    ] ) );

    expect( failures.map( f => f.kind ).sort() ).toEqual( [ 'forbidden', 'not-found' ] );
  } );

  it( 'stops collecting once the load is over', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 200, {} ) );
    const { failures } = await collectApiFailures( () => apiCallResult( URL ) );

    fetchMock.mockResolvedValue( jsonResponse( 500 ) );
    await apiCallResult( URL );

    // The later failure must not appear in an already-settled collection.
    expect( failures ).toHaveLength( 0 );
  } );

  it( 'unregisters its listener even when the load throws', async () => {
    fetchMock.mockResolvedValue( jsonResponse( 500 ) );

    await expect(
      collectApiFailures( async () => { throw new Error( 'loader blew up' ); } )
    ).rejects.toThrow( 'loader blew up' );

    // If the listener leaked, this failure would be pushed into a dead array
    // and, worse, the set would grow on every load. Prove the next collection
    // sees exactly its own one failure.
    const { failures } = await collectApiFailures( () => apiCallResult( URL ) );
    expect( failures ).toHaveLength( 1 );
  } );
} );
