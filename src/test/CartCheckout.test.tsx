import React from 'react';
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';

import * as cart from '../lib/cart';
import type { ShopProduct } from '../content/shop';
import * as customerAuth from '../lib/customerAuth';
import Cart from '../pages/cart';

/**
 * The /shop/ -> Cart V2 -> checkout wiring, tested the way ShopCatalogue.test.tsx tests the
 * catalogue: against mocked fetch and mocked storage, asserting logic and DOM presence only. jsdom
 * cannot read a computed style, so the design system (lime CTA, dark-green price, clearances) is
 * left to the browser harnesses; here we prove the CONTRACT.
 *
 * The four load-bearing properties, each its own describe:
 *   1. the cart store round-trips and is SSR-safe;
 *   2. toLineItems() emits references and quantities ONLY - no price-like key ever reaches the wire;
 *   3. a PAYMENT_INITIATION_DISABLED response reaches the honest outcome and renders no pay button;
 *   4. proceeding with no session routes to sign-in and never calls the create endpoint;
 *   plus a 409 readiness-blocked mapping to the "no charge was made" copy.
 */

const PRODUCT: ShopProduct = {
  id: 'wix-abc-123',
  name: 'Kiosk',
  slug: 'kiosk',
  formattedPrice: '₹24,999.00',
  price: '24999.00',
  currency: 'INR',
  inStock: true,
  tagline: 'Put your location to work.',
  body: [ 'You already have the place.' ],
};

const OTHER: ShopProduct = {
  id: 'wix-def-456',
  name: 'Merchandise',
  slug: 'merchandise',
  formattedPrice: '₹599.00',
  price: '599.00',
  currency: 'INR',
  inStock: true,
  tagline: 'Wear it.',
  body: [ 'A shirt.' ],
};

/** Capture where the page tries to navigate, without jsdom's "not implemented" throw. */
let navigatedTo: string;

beforeEach( () => {
  window.localStorage.clear();
  navigatedTo = '';
  Object.defineProperty( window, 'location', {
    configurable: true,
    value: {
      ...window.location,
      search: '',
      assign: ( url: string ) => { navigatedTo = String( url ); },
      replace: ( url: string ) => { navigatedTo = String( url ); },
    },
  } );
} );

afterEach( () => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
} );

describe( 'the cart store', () => {
  it( 'adds, increments the same reference, and reports a count', () => {
    cart.addItem( PRODUCT, 1 );
    cart.addItem( PRODUCT, 2 );
    const items = cart.readCart();
    expect( items ).toHaveLength( 1 );
    expect( items[ 0 ].ref ).toBe( 'wix-abc-123' );
    expect( items[ 0 ].quantity ).toBe( 3 );
    expect( cart.cartCount() ).toBe( 3 );
  } );

  it( 'keeps distinct products as distinct lines', () => {
    cart.addItem( PRODUCT, 1 );
    cart.addItem( OTHER, 1 );
    expect( cart.readCart().map( i => i.ref ) ).toEqual( [ 'wix-abc-123', 'wix-def-456' ] );
  } );

  it( 'sets an exact quantity and removes a line when it hits zero', () => {
    cart.addItem( PRODUCT, 1 );
    cart.setQuantity( 'wix-abc-123', 5 );
    expect( cart.readCart()[ 0 ].quantity ).toBe( 5 );
    cart.setQuantity( 'wix-abc-123', 0 );
    expect( cart.readCart() ).toHaveLength( 0 );
  } );

  it( 'removes a line and clears the whole cart', () => {
    cart.addItem( PRODUCT, 1 );
    cart.addItem( OTHER, 1 );
    cart.removeItem( 'wix-abc-123' );
    expect( cart.readCart().map( i => i.ref ) ).toEqual( [ 'wix-def-456' ] );
    cart.clearCart();
    expect( cart.readCart() ).toHaveLength( 0 );
  } );

  it( 'survives a round-trip through storage', () => {
    cart.addItem( PRODUCT, 2 );
    // A fresh read parses what is actually persisted, not in-memory state.
    const raw = window.localStorage.getItem( 'wecare.cart.v1' );
    expect( raw ).toBeTruthy();
    expect( cart.readCart()[ 0 ].quantity ).toBe( 2 );
  } );

  it( 'tolerates corrupt storage rather than throwing', () => {
    window.localStorage.setItem( 'wecare.cart.v1', 'not json' );
    expect( cart.readCart() ).toEqual( [] );
  } );

  it( 'is SSR-safe: reads return empty and writes are no-ops when window is undefined', () => {
    const realWindow = globalThis.window;
    // Simulate the server: no window at all. The guards in cart.ts must not touch storage.
    // @ts-expect-error deliberately removing window to exercise the SSR guard
    delete globalThis.window;
    try
    {
      expect( cart.readCart() ).toEqual( [] );
      expect( cart.cartCount() ).toBe( 0 );
      expect( () => cart.clearCart() ).not.toThrow();
      expect( () => cart.addItem( PRODUCT, 1 ) ).not.toThrow();
    }
    finally
    {
      globalThis.window = realWindow;
    }
  } );
} );

describe( 'toLineItems emits references and quantities ONLY', () => {
  it( 'maps each line to { catalogReference, quantity } and nothing else', () => {
    cart.addItem( PRODUCT, 2 );
    cart.addItem( OTHER, 1 );
    const lineItems = cart.toLineItems();
    expect( lineItems ).toEqual( [
      { catalogReference: 'wix-abc-123', quantity: 2 },
      { catalogReference: 'wix-def-456', quantity: 1 },
    ] );
    for ( const item of lineItems )
    {
      expect( Object.keys( item ).sort() ).toEqual( [ 'catalogReference', 'quantity' ] );
    }
  } );

  it( 'serialises with no price-like key anywhere in the payload', () => {
    // THE RULE THE WHOLE ARCHITECTURE RESTS ON: the browser never sends a financial figure. Assert
    // on the serialised string the fetch body would carry, so a stray key cannot slip through.
    cart.addItem( PRODUCT, 3 );
    const serialised = JSON.stringify( { action: 'create', lineItems: cart.toLineItems() } );
    for ( const forbidden of [ 'price', 'amount', 'formattedPrice', 'currency', 'total', 'paise' ] )
    {
      expect( serialised.toLowerCase() ).not.toContain( forbidden.toLowerCase() );
    }
    // The display price the cart holds must not have leaked into the payload.
    expect( serialised ).not.toContain( '24,999' );
    expect( serialised ).not.toContain( '24999' );
  } );
} );

describe( 'the cart page proceed flow', () => {
  it( 'routes an anonymous shopper to sign-in and never calls create', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    const fetchMock = vi.fn();
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );

    await waitFor( () => expect( navigatedTo ).toContain( '/account/sign-in' ) );
    expect( navigatedTo ).toContain( 'return=/cart/' );
    // The auth gate must short-circuit BEFORE any create request.
    expect( fetchMock ).not.toHaveBeenCalled();
  } );

  it( 'sends { action:create, lineItems } with a Bearer token, refs+quantities only', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    const fetchMock = vi.fn().mockResolvedValue( {
      ok: true,
      status: 200,
      json: async () => ( {
        status: 'PAYMENT_INITIATION_DISABLED', paymentAttemptId: 'att-1', currency: 'INR',
      } ),
    } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 2 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 1 ) );
    const [ url, init ] = fetchMock.mock.calls[ 0 ];
    expect( String( url ) ).toContain( '/ecommerce/checkout' );
    expect( ( init.headers as Record<string, string> ).Authorization ).toBe( 'Bearer tok-123' );
    const body = JSON.parse( init.body as string );
    expect( body.action ).toBe( 'create' );
    expect( body.lineItems ).toEqual( [ { catalogReference: 'wix-abc-123', quantity: 2 } ] );
    // No financial figure on the wire.
    expect( init.body as string ).not.toMatch( /price|amount|currency|formattedPrice/i );
  } );

  it( 'sends PAYMENT_INITIATION_DISABLED to the hosted status screen with no pay button', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true,
      status: 200,
      json: async () => ( { status: 'PAYMENT_INITIATION_DISABLED', paymentAttemptId: 'att-9' } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );

    // The honest outcome: hand off to the reused hosted status screen, which maps this status to
    // the neutral 'unavailable' view. Never a pay-now / charge affordance anywhere on the page.
    await waitFor( () => expect( navigatedTo ).toBe( '/checkout/status/?a=att-9' ) );
    expect( screen.queryByRole( 'button', { name: /pay/i } ) ).toBeNull();
    expect( container.textContent || '' ).not.toMatch( /pay now|pay \u20b9|make payment/i );
    // The prepared cart is cleared so it cannot be re-submitted.
    expect( cart.readCart() ).toHaveLength( 0 );
  } );

  it( 'routes PAYMENT_REQUEST_SENT to the hosted status screen', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true,
      status: 200,
      json: async () => ( { status: 'PAYMENT_REQUEST_SENT', paymentAttemptId: 'att-5' } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );
    await waitFor( () => expect( navigatedTo ).toBe( '/checkout/status/?a=att-5' ) );
  } );

  it( 'shows "no charge was made" on a 409 readiness block, staying on the page', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false,
      status: 409,
      json: async () => ( {
        status: 'payment_unavailable', readiness: 'CONFIGURATION_UNVERIFIED',
        message: 'Payments are temporarily unavailable. No charge was made.',
      } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );

    expect( await screen.findByText( /No charge was made/ ) ).toBeTruthy();
    // It did not pretend to succeed or navigate away.
    expect( navigatedTo ).toBe( '' );
    expect( screen.queryByRole( 'button', { name: /pay/i } ) ).toBeNull();
  } );

  it( 'offers a retry with no charge on a 502 SEND_FAILED', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false,
      status: 502,
      json: async () => ( { status: 'SEND_FAILED', paymentAttemptId: 'att-2' } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );
    expect( await screen.findByText( /No charge was made - please try again/ ) ).toBeTruthy();
  } );

  it( 'sends a 401 back to sign-in', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 401, json: async () => ( {} ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed to checkout' } ) );
    await waitFor( () => expect( navigatedTo ).toContain( '/account/sign-in' ) );
  } );

  it( 'shows an empty state and no proceed button when the cart is empty', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    render( <Cart /> );
    expect( await screen.findByText( 'Your cart is empty.' ) ).toBeTruthy();
    expect( screen.queryByRole( 'button', { name: 'Proceed to checkout' } ) ).toBeNull();
  } );
} );
