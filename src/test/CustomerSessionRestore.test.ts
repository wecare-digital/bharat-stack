import { afterEach, beforeEach, expect, it, vi } from 'vitest';

beforeEach( () => { window.localStorage.clear(); window.sessionStorage.clear(); vi.resetModules(); } );
afterEach( () => { vi.unstubAllGlobals(); vi.restoreAllMocks(); } );
const hint = { csrfToken: 'qa-csrf', expiresAt: Date.now() + 86_400_000, persistent: true };
const response = ( body: unknown, status = 200 ) => ({ ok: status === 200, status,
  text: async () => JSON.stringify( body ), json: async () => body });

it( 'exchanges refresh custody without persisting the refresh token in browser storage', async () => {
  const fetchMock = vi.fn().mockResolvedValueOnce( response( {
    AuthenticationResult: { AccessToken: 'qa-access', RefreshToken: 'qa-refresh', ExpiresIn: 3600 },
  } ) ).mockResolvedValueOnce( response( hint ) );
  vi.stubGlobal( 'fetch', fetchMock );
  const auth = await import( '../lib/customerAuth' );
  await auth.submitOtp( '+910000000000', '000000', 'qa-challenge' );
  expect( fetchMock.mock.calls[1][0] ).toBe( '/api/ecommerce/customer-session' );
  expect( fetchMock.mock.calls[1][1].credentials ).toBe( 'same-origin' );
  expect( JSON.stringify( { ...window.localStorage, ...window.sessionStorage } ) ).not.toContain( 'qa-refresh' );
} );

it( 'restores a new tab silently and shares one refresh between simultaneous requests', async () => {
  window.localStorage.setItem( 'wecare.customer.sessionHint', JSON.stringify( hint ) );
  const fetchMock = vi.fn().mockResolvedValue( response( { accessToken: 'qa-renewed', expiresAt: Date.now() + 3_600_000 } ) );
  vi.stubGlobal( 'fetch', fetchMock );
  const auth = await import( '../lib/customerAuth' );
  const sessions = await Promise.all( [ auth.restoreSession(), auth.restoreSession() ] );
  expect( fetchMock ).toHaveBeenCalledTimes( 1 );
  expect( sessions.every( session => session?.accessToken === 'qa-renewed' ) ).toBe( true );
  expect( fetchMock.mock.calls[0][1].headers['X-Customer-CSRF'] ).toBe( 'qa-csrf' );
} );

it( 'keeps remembered login during a provider outage and removes it on definite expiry', async () => {
  window.localStorage.setItem( 'wecare.customer.sessionHint', JSON.stringify( hint ) );
  const fetchMock = vi.fn().mockResolvedValueOnce( response( {}, 503 ) ).mockResolvedValueOnce( response( {}, 401 ) );
  vi.stubGlobal( 'fetch', fetchMock );
  const auth = await import( '../lib/customerAuth' );
  await expect( auth.restoreSession() ).rejects.toThrow( /temporarily/ );
  expect( window.localStorage.getItem( 'wecare.customer.sessionHint' ) ).not.toBeNull();
  expect( await auth.restoreSession() ).toBeNull();
  expect( window.localStorage.getItem( 'wecare.customer.sessionHint' ) ).toBeNull();
} );

it( 'does not revoke remembered login merely because the access token expired', async () => {
  window.localStorage.setItem( 'wecare.customer.sessionHint', JSON.stringify( hint ) );
  const auth = await import( '../lib/customerAuth' );
  auth.storeSession( 'qa-expired', Date.now() - 1000 );
  expect( auth.getSession() ).toBeNull();
  expect( window.localStorage.getItem( 'wecare.customer.sessionHint' ) ).not.toBeNull();
} );

it( 'drops a cached token after logout in another tab', async () => {
  const auth = await import( '../lib/customerAuth' );
  auth.storeSession( 'qa-access', Date.now() + 3_600_000 );
  window.dispatchEvent( new StorageEvent( 'storage', {
    key: 'wecare.customer.sessionHint', oldValue: JSON.stringify( hint ), newValue: null,
  } ) );
  expect( auth.getSession() ).toBeNull();
} );

it( 'preserves an explicit country prefix rather than treating it as an Indian local number', async () => {
  const auth = await import( '../lib/customerAuth' );
  expect( auth.normaliseMobile( '+61 1234 5678' ) ).toBe( '+6112345678' );
  expect( auth.normaliseMobile( '9876543210' ) ).toBe( '+919876543210' );
} );
