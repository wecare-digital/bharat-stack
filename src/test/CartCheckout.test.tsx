import React from 'react';
import {
  afterEach, beforeEach, describe, expect, it, vi,
} from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import fs from 'fs';
import path from 'path';

import * as cart from '../lib/cart';
import type { ShopProduct } from '../content/shop';
import * as customerAuth from '../lib/customerAuth';

vi.mock( '../components/CheckoutProfile', () => ( {
  default: ( { onReady }: { onReady: ( value: Record<string, string> ) => void } ) => (
    <button
      type="button"
      onClick={ () => onReady( {
        contactId: 'contact-1',
        name: 'Asha Sen',
        email: 'asha@example.com',
        phone: '+919330994400',
      } ) }
    >
      Complete checkout details
    </button>
  ),
} ) );

import Cart from '../pages/cart';
import CheckoutStatus, { viewFor } from '../pages/checkout/status';

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
  window.sessionStorage.clear();
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

async function proceedPastProfile (): Promise<void> {
  fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed' } ) );
  fireEvent.click( await screen.findByRole( 'button', { name: 'Complete checkout details' } ) );
  fireEvent.click( await screen.findByRole( 'button', { name: /Pay securely/ } ) );
}

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
      { catalogReference: { appId: '215238eb-22a5-4c36-9e7b-e7c08025e04e', catalogItemId: 'wix-abc-123' }, quantity: 2 },
      { catalogReference: { appId: '215238eb-22a5-4c36-9e7b-e7c08025e04e', catalogItemId: 'wix-def-456' }, quantity: 1 },
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
    fireEvent.click( await screen.findByRole( 'button', { name: 'Proceed' } ) );

    await waitFor( () => expect( navigatedTo ).toContain( '/account/sign-in' ) );
    expect( navigatedTo ).toContain( 'return=/cart/' );
    // The auth gate must short-circuit BEFORE any create request.
    expect( fetchMock ).not.toHaveBeenCalled();
  } );

  it( 'sends { action:prepare, lineItems, requestKey } with a Bearer token and no money', async () => {
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
    await proceedPastProfile();

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 1 ) );
    const [ url, init ] = fetchMock.mock.calls[ 0 ];
    expect( String( url ) ).toContain( '/ecommerce/prepare-checkout' );
    expect( ( init.headers as Record<string, string> ).Authorization ).toBe( 'Bearer tok-123' );
    const body = JSON.parse( init.body as string );
    expect( body.action ).toBe( 'prepare' );
    expect( typeof body.requestKey ).toBe( 'string' );
    expect( body.requestKey.length ).toBeGreaterThan( 8 );
    expect( body.lineItems ).toEqual( [ { catalogReference: { appId: '215238eb-22a5-4c36-9e7b-e7c08025e04e', catalogItemId: 'wix-abc-123' }, quantity: 2 } ] );
    // No financial figure on the wire.
    expect( init.body as string ).not.toMatch( /price|amount|currency|formattedPrice/i );
  } );

  it( 'answers PAYMENT_INITIATION_DISABLED inline, keeps the cart, and offers no pay button', async () => {
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
    await proceedPastProfile();

    /*
     * TWO PINNED BEHAVIOURS CHANGED HERE, AND BOTH WERE WRONG BEFORE.
     *
     * 1. IT NO LONGER NAVIGATES to /checkout/status/?a=att-9. The approved sentence asserts that no
     *    charge was made, and this status - the server's own initiation gate being off - is one of
     *    the few responses that can support that claim. The status screen cannot carry it: its
     *    viewFor() folds this status in with "we cannot find this attempt" and anything
     *    unrecognised, states where the money may in fact have moved, and PublicPageTopBand.test
     *    pins that /checkout/status/ never says "no charge" in ANY state. So the sentence has to be
     *    shown by the page that received the response, where it stays pinned to its evidence.
     *
     * 2. THE CART IS NO LONGER CLEARED. It was, alongside the genuinely-in-flight case. That left a
     *    shopper nothing to come back to when the gate is simply off - and because the notice
     *    renders inside the items list, clearing the cart would have replaced the explanation with
     *    "Your cart is empty." The recorded attempt is not payable, so the cart is still theirs.
     *
     * What has NOT changed is the invariant the old test existed to protect: no pay-now affordance
     * and no charge claim in the wrong direction.
     */
    expect( await screen.findByText(
      'We could not prepare this order. No charge was made - please try again shortly.',
    ) ).toBeTruthy();
    expect( navigatedTo ).toBe( '' );
    expect( cart.readCart() ).toHaveLength( 1 );
    expect( screen.queryByRole( 'button', { name: /pay/i } ) ).toBeNull();
    expect( container.textContent || '' ).not.toMatch( /pay now|pay \u20b9|make payment/i );
  } );

  it( 'opens Razorpay with server options and verifies the returned callback before navigation', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'fixture-session', expiresAt: Date.now() + 3_600_000,
    } );

    let receivedOptions: any = null;
    const open = vi.fn();
    class FakeRazorpay {
      constructor ( options: any ) { receivedOptions = options; }
      open = open;
      on = vi.fn();
    }
    Object.defineProperty( window, 'Razorpay', {
      configurable: true,
      writable: true,
      value: FakeRazorpay,
    } );

    const fetchMock = vi.fn()
      .mockResolvedValueOnce( {
        ok: true,
        status: 200,
        json: async () => ( {
          status: 'CHECKOUT_OPTIONS_READY',
          paymentAttemptId: 'att-web-1',
          options: {
            keyId: 'fixture-publishable-id',
            orderId: 'order-fixture-1',
            amountPaise: 121481,
            currency: 'INR',
            prefill: {
              name: 'Asha Sen',
              email: 'asha@example.com',
              contact: '+919330994400',
            },
          },
        } ),
      } )
      .mockResolvedValueOnce( {
        ok: true,
        status: 200,
        json: async () => ( {
          status: 'VERIFIED_PAID',
          paymentAttemptId: 'att-web-1',
        } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    await proceedPastProfile();

    await waitFor( () => expect( open ).toHaveBeenCalledTimes( 1 ) );
    expect( receivedOptions.order_id ).toBe( 'order-fixture-1' );
    expect( receivedOptions.amount ).toBe( 121481 );
    expect( receivedOptions.currency ).toBe( 'INR' );
    expect( receivedOptions.prefill.email ).toBe( 'asha@example.com' );
    expect( receivedOptions ).not.toHaveProperty( 'key_secret' );

    const prepareBody = JSON.parse( fetchMock.mock.calls[ 0 ][ 1 ].body );
    expect( prepareBody.action ).toBe( 'prepare' );
    expect( prepareBody ).not.toHaveProperty( 'amountPaise' );
    expect( prepareBody ).not.toHaveProperty( 'currency' );
    expect( typeof prepareBody.requestKey ).toBe( 'string' );

    await receivedOptions.handler( {
      razorpay_payment_id: 'payment-fixture-1',
      razorpay_order_id: 'order-fixture-1',
      razorpay_signature: 'signature-fixture',
    } );

    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 2 ) );
    const verifyBody = JSON.parse( fetchMock.mock.calls[ 1 ][ 1 ].body );
    expect( verifyBody ).toEqual( {
      action: 'verify',
      razorpay_payment_id: 'payment-fixture-1',
      razorpay_order_id: 'order-fixture-1',
      razorpay_signature: 'signature-fixture',
    } );
    expect( navigatedTo ).toBe( '/checkout/status/?a=att-web-1' );
    expect( cart.readCart() ).toHaveLength( 1 );
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
    await proceedPastProfile();
    await waitFor( () => expect( navigatedTo ).toBe( '/checkout/status/?a=att-5' ) );
    expect( cart.readCart() ).toHaveLength( 1 );
  } );

  it.each( [ 'network', 'server' ] )( 'preserves the cart and makes no charge claim after a %s failure', async failure => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    const fetchMock = failure === 'network'
      ? vi.fn().mockRejectedValue( new TypeError( 'response lost' ) )
      : vi.fn().mockResolvedValue( { ok: false, status: 500, json: async () => ( {} ) } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );
    const { container } = render( <Cart /> );
    await proceedPastProfile();
    expect( await screen.findByText( 'We could not confirm checkout. Check your orders before trying again.' ) ).toBeTruthy();
    expect( container.textContent ).not.toMatch( /No charge was made/i );
    expect( cart.readCart() ).toHaveLength( 1 );
    expect( navigatedTo ).toBe( '' );
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
    await proceedPastProfile();

    expect( await screen.findByText( /No charge was made/ ) ).toBeTruthy();
    // THE EXACT APPROVED SENTENCE, not merely something containing "No charge was made". A readiness
    // refusal is the other response that genuinely never reached the payment rail, so it earns the
    // same words as the disabled gate rather than a near-miss paraphrase. Note the server's own
    // `message` field is deliberately NOT rendered: the copy on this page is ours to control.
    expect( await screen.findByText(
      'We could not prepare this order. No charge was made - please try again shortly.',
    ) ).toBeTruthy();
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
    await proceedPastProfile();
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
    await proceedPastProfile();
    await waitFor( () => expect( navigatedTo ).toContain( '/account/sign-in' ) );
  } );

  it( 'shows an empty state and no proceed button when the cart is empty', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( null );
    render( <Cart /> );
    expect( await screen.findByText( 'Your cart is empty.' ) ).toBeTruthy();
    expect( screen.queryByRole( 'button', { name: 'Proceed' } ) ).toBeNull();
  } );
} );

/**
 * WHERE THE APPROVED SENTENCE MAY AND MAY NOT APPEAR.
 *
 * "We could not prepare this order. No charge was made - please try again shortly." asserts a
 * financial fact. On an initiation refusal that fact is backed by the server's own response. On a
 * pending, unknown or captured-but-unfinalised attempt it is not knowable from the browser at all,
 * and offering a retry there risks a second charge for money that has already moved. So the sentence
 * is tested from both directions: present where the evidence exists, absent everywhere else.
 */
describe( 'the initiation-failure sentence is pinned to its evidence', () => {
  const SENTENCE = 'We could not prepare this order. No charge was made - please try again shortly.';

  it( 'is the exact wording on every initiation-refusal branch', async () => {
    // Four distinct refusals, all of which mean the request did not reach the payment rail. Each
    // must produce the sentence CHARACTER FOR CHARACTER - a paraphrase is a different promise, and
    // the hyphen in "made - please" is part of the approved string.
    const refusals: Array<{ ok: boolean; status: number; body: unknown }> = [
      { ok: true, status: 200, body: { status: 'PAYMENT_INITIATION_DISABLED', paymentAttemptId: 'att-d' } },
      { ok: false, status: 409, body: { status: 'payment_unavailable' } },
      { ok: false, status: 422, body: { status: 'UNSUPPORTED_CURRENCY' } },
      { ok: false, status: 503, body: { status: 'CATALOGUE_UNAVAILABLE' } },
    ];

    for ( const refusal of refusals )
    {
      window.localStorage.clear();
      navigatedTo = '';
      vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
        accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
      } );
      vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
        ok: refusal.ok, status: refusal.status, json: async () => refusal.body,
      } ) );
      cart.addItem( PRODUCT, 1 );

      const { unmount } = render( <Cart /> );
      await proceedPastProfile();
      expect( await screen.findByText( SENTENCE ), JSON.stringify( refusal.body ) ).toBeTruthy();
      // Nothing was handed off, so the claim stays attached to the response that justified it.
      expect( navigatedTo ).toBe( '' );
      unmount();
      vi.restoreAllMocks();
      vi.unstubAllGlobals();
    }
  } );

  it( 'is absent from the in-flight handoff, which claims nothing either way', async () => {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'tok-123', expiresAt: Date.now() + 3_600_000,
    } );
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true, status: 200,
      json: async () => ( { status: 'PAYMENT_REQUEST_SENT', paymentAttemptId: 'att-5' } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();

    await waitFor( () => expect( navigatedTo ).toBe( '/checkout/status/?a=att-5' ) );
    expect( cart.readCart() ).toHaveLength( 1 );
    // ONCE A REQUEST HAS LEFT, the browser cannot rule out a capture, so neither the sentence nor
    // any part of its claim may be rendered on the way out.
    expect( container.textContent || '' ).not.toContain( SENTENCE );
    expect( container.textContent || '' ).not.toMatch( /no charge/i );
  } );

  it( 'is absent from the status screen in pending, paid-finalizing and unknown states', () => {
    /*
     * THE DIRECTION THAT MATTERS MOST. These are the states where money may already have moved:
     * PAYMENT_PENDING is in flight, PAYMENT_PAID without an order number is captured but not
     * finalised, and an empty or unrecognised status means we simply do not know. Telling any of
     * those three "no charge was made - please try again" invites a double charge.
     */
    for ( const [ status, orderNumber, expected ] of [
      [ 'PAYMENT_PENDING', null, 'confirming' ],
      [ 'PAYMENT_REQUEST_SENT', null, 'confirming' ],
      [ 'PAYMENT_PAID', null, 'finalizing' ],
      [ '', null, 'unavailable' ],
      [ 'SOMETHING_NEW_FROM_THE_BACKEND', null, 'unavailable' ],
      [ 'PAYMENT_INITIATION_DISABLED', null, 'unavailable' ],
    ] as [ string, string | null, string ][] )
    {
      // The mapping is asserted alongside the copy so a future view rename cannot quietly route a
      // pending attempt into a screen that does make the claim.
      expect( viewFor( status, orderNumber ) ).toBe( expected );
      const { container, unmount } = render( <CheckoutStatus /> );
      expect( container.textContent || '' ).not.toContain( SENTENCE );
      unmount();
    }

    // And the sentence is not in the file at all, in any state this test did not think to render.
    // PAYMENT_INITIATION_DISABLED lands on 'unavailable' here TOO, shared with "we cannot find
    // this attempt" - which is precisely why the sentence lives on /cart/ and not on this screen.
    const source = fs.readFileSync(
      path.join( process.cwd(), 'src/pages/checkout/status.tsx' ), 'utf8',
    ).replace( /\/\*[\s\S]*?\*\//g, '' ).replace( /^\s*\/\/.*$/gm, '' );
    expect( source ).not.toContain( SENTENCE );
    expect( source.toLowerCase() ).not.toContain( 'no charge' );
  } );
} );


/*
 * ── the terminal latch, and the full stubbed rail ─────────────────────────────
 *
 * The CTA sits underneath the Razorpay modal with `disabled={busy}` and `busy` goes false the
 * moment `razorpay.open()` returns, so before this latch the Proceed pill was live behind an open
 * payment modal and live again after a verify response that said "we are still verifying".
 *
 * Every assertion below is POSITIVE -- a call count, a URL, `pill === null || pill.disabled`.
 * A `queryBy*` returning `null` on its own asserts nothing, because a renamed element returns
 * null too. The CTA's accessible name is one of `Checkout Proceed`, `Checkout Pay securely` or
 * `Checkout Try again`, so it is found by ROLE AND POSITION inside the `cart-pill` region rather
 * than by a guessed name.
 *
 * The latch is DEFENCE IN DEPTH, not the guarantee: it dies with the page. The server-side
 * one-live-payment-per-basket guard is the guarantee, and it is tested in
 * `tests/test_graft_money_correctness.py`.
 */
describe( 'the payment rail latches once it has returned a result', () => {
  function pillButton ( container: HTMLElement ): HTMLButtonElement | null {
    const region = container.querySelector( '.cart-pill' );
    return region ? region.querySelector( 'button' ) : null;
  }

  function fakeRazorpay () {
    const state: { options: any; opens: number; events: string[] } = {
      options: null, opens: 0, events: [],
    };
    class FakeRazorpay {
      constructor ( options: any ) { state.options = options; }
      open = () => {
        // NEVER any network I/O: the SDK is stubbed precisely so no real charge is possible.
        state.opens += 1;
      };
      on = ( event: string ) => { state.events.push( event ); };
    }
    Object.defineProperty( window, 'Razorpay', {
      configurable: true, writable: true, value: FakeRazorpay,
    } );
    return state;
  }

  const READY_OPTIONS = {
    status: 'CHECKOUT_OPTIONS_READY',
    paymentAttemptId: 'att-latch-1',
    options: {
      keyId: 'fixture-publishable-id',
      orderId: 'order-latch-1',
      amountPaise: 2625123,
      currency: 'INR',
      prefill: { name: 'Asha Sen', email: 'asha@example.com', contact: '+919330994400' },
      paymentAttemptId: 'att-latch-1',
    },
  };

  function signedIn () {
    vi.spyOn( customerAuth, 'getSession' ).mockReturnValue( {
      accessToken: 'fixture-session', expiresAt: Date.now() + 3_600_000,
    } );
  }

  it( 'the full stubbed rail: cart -> profile -> prepare -> modal -> verify -> one order', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, status: 200, json: async () => READY_OPTIONS } )
      .mockResolvedValueOnce( {
        ok: true, status: 200,
        json: async () => ( {
          status: 'VERIFIED_PAID', paymentAttemptId: 'att-latch-1',
          orderNumber: 'WD-ORD-A1B2C3D4',
        } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();

    // The modal payload, asserted as an allow-list rather than a spot check.
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );
    expect( razorpay.options.order_id ).toBe( 'order-latch-1' );
    expect( Number.isInteger( razorpay.options.amount ) ).toBe( true );
    expect( razorpay.options.amount ).toBe( 2625123 );
    expect( razorpay.options.currency ).toBe( 'INR' );
    expect( razorpay.options.key ).toBe( 'fixture-publishable-id' );
    expect( String( razorpay.options.order_id ).length ).toBeGreaterThan( 0 );
    // No key whose name mentions a secret, anywhere in what the browser was handed.
    const handed = Object.keys( razorpay.options );
    expect( handed.filter( ( key ) => /secret/i.test( key ) ) ).toEqual( [] );
    expect( JSON.stringify( razorpay.options ) ).not.toMatch( /secret/i );

    // Exactly one verify POST, to the verify route.
    await razorpay.options.handler( {
      razorpay_payment_id: 'pay-latch-1',
      razorpay_order_id: 'order-latch-1',
      razorpay_signature: 'sig-latch-1',
    } );
    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 2 ) );
    expect( String( fetchMock.mock.calls[ 1 ][ 0 ] ) ).toContain( '/ecommerce/verify-callback' );
    const verifyBodies = fetchMock.mock.calls
      .map( ( call: any[] ) => JSON.parse( call[ 1 ].body ) )
      .filter( ( body: any ) => body.action === 'verify' );
    expect( verifyBodies ).toHaveLength( 1 );

    // ...and one navigation to the status page for that one attempt.
    expect( navigatedTo ).toBe( '/checkout/status/?a=att-latch-1' );
  } );

  it( 'latches on a VERIFIED_PAID return, so the CTA cannot re-enter the rail', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, status: 200, json: async () => READY_OPTIONS } )
      .mockResolvedValueOnce( {
        ok: true, status: 200,
        json: async () => ( { status: 'VERIFIED_PAID', paymentAttemptId: 'att-latch-1' } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );

    await razorpay.options.handler( {
      razorpay_payment_id: 'pay-latch-1',
      razorpay_order_id: 'order-latch-1',
      razorpay_signature: 'sig-latch-1',
    } );
    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 2 ) );

    // The pill is either gone (replaced by the orders link) or disabled. Asserted as the
    // DISJUNCTION, so it passes under both mechanisms and cannot be satisfied by a live button.
    const pill = pillButton( container );
    expect( pill === null || pill.disabled ).toBe( true );
    // And the way off the page is a LINK, whose words cannot read as "pay again".
    const away = container.querySelector( '.cart-pill a' ) as HTMLAnchorElement | null;
    expect( away ).toBeTruthy();
    expect( String( away?.textContent || '' ) ).toBe( 'Check your orders' );
    expect( String( away?.textContent || '' ) ).not.toMatch( /pay|again|retry/i );
  } );

  it( 'latches on a LOST verify response, which is the case money may have moved in', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, status: 200, json: async () => READY_OPTIONS } )
      // The verify request THROWS. Nothing came back to read, so a live CTA here is the worst
      // possible affordance: the payment may well have succeeded.
      .mockRejectedValueOnce( new Error( 'network' ) );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );

    await razorpay.options.handler( {
      razorpay_payment_id: 'pay-latch-1',
      razorpay_order_id: 'order-latch-1',
      razorpay_signature: 'sig-latch-1',
    } );

    // `waitFor`, because the latch is set as the handler's FIRST statement -- before the fetch
    // that then throws -- so the state update has to be flushed before the render is read. That
    // ordering is the point of the row: the latch holds even though nothing came back.
    await waitFor( () => {
      const pill = pillButton( container );
      expect( pill === null || pill.disabled ).toBe( true );
    } );
    expect( navigatedTo ).toBe( '' );
    // The copy makes no claim about a charge in either direction.
    expect( container.textContent || '' ).not.toMatch( /no charge/i );
  } );

  it( 'latches on a non-VERIFIED_PAID verdict too, because the money is still unknown', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    const fetchMock = vi.fn()
      .mockResolvedValueOnce( { ok: true, status: 200, json: async () => READY_OPTIONS } )
      .mockResolvedValueOnce( {
        ok: true, status: 200,
        json: async () => ( { status: 'NOT_CAPTURED', paymentAttemptId: 'att-latch-1' } ),
      } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );
    await razorpay.options.handler( {
      razorpay_payment_id: 'pay-latch-1',
      razorpay_order_id: 'order-latch-1',
      razorpay_signature: 'sig-latch-1',
    } );
    await waitFor( () => expect( fetchMock ).toHaveBeenCalledTimes( 2 ) );

    const pill = pillButton( container );
    expect( pill === null || pill.disabled ).toBe( true );
    expect( navigatedTo ).toBe( '' );
  } );

  it( 'does NOT latch on a dismissed modal, because nothing came back to verify', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    const fetchMock = vi.fn()
      .mockResolvedValue( { ok: true, status: 200, json: async () => READY_OPTIONS } );
    vi.stubGlobal( 'fetch', fetchMock );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );

    // A dismissal means the provider took nothing, and the next click re-presents the SAME stored
    // request key onto the SAME gateway order. Latching it would strand a shopper who closed the
    // modal by accident.
    razorpay.options.modal.ondismiss();
    const pill = pillButton( container );
    expect( pill ).toBeTruthy();
    expect( pill?.disabled ).toBe( false );
  } );

  it( 'registers payment.failed and does not latch on it either', async () => {
    signedIn();
    const razorpay = fakeRazorpay();
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: true, status: 200, json: async () => READY_OPTIONS,
    } ) );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( razorpay.opens ).toBe( 1 ) );
    // The provider is telling us no money moved, so the rail is re-enterable.
    expect( razorpay.events ).toContain( 'payment.failed' );
    const pill = pillButton( container );
    expect( pill ).toBeTruthy();
    expect( pill?.disabled ).toBe( false );
  } );

  it( 'an ambiguous refusal WITH an attempt id goes to the status page', async () => {
    signedIn();
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 409,
      json: async () => ( {
        status: 'CHECKOUT_AMBIGUOUS', reason: 'CART_ALREADY_PAID',
        paymentAttemptId: 'att-blocked-1',
      } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    render( <Cart /> );
    await proceedPastProfile();
    await waitFor( () => expect( navigatedTo ).toBe( '/checkout/status/?a=att-blocked-1' ) );
  } );

  it( 'an ambiguous refusal with NO attempt id claims nothing about a charge', async () => {
    signedIn();
    vi.stubGlobal( 'fetch', vi.fn().mockResolvedValue( {
      ok: false, status: 409,
      json: async () => ( {
        status: 'CHECKOUT_AMBIGUOUS', reason: 'CART_PAYMENT_IN_FLIGHT',
      } ),
    } ) );
    cart.addItem( PRODUCT, 1 );

    const { container } = render( <Cart /> );
    await proceedPastProfile();

    // A step-4b loser deliberately carries no attempt id, because the holder's attempt may not
    // exist yet and an unresolvable id would point the status page at nothing. So this falls to
    // the charge-silent catch-all: no navigation, no claim either way, CTA still live for a retry
    // that will succeed once the winner's row is recorded.
    await waitFor( () => expect(
      ( container.textContent || '' ).length ).toBeGreaterThan( 0 ) );
    expect( navigatedTo ).toBe( '' );
    expect( container.textContent || '' ).not.toMatch( /no charge/i );
    const pill = pillButton( container );
    expect( pill ).toBeTruthy();
    expect( pill?.disabled ).toBe( false );
  } );

  it( 'has no INTENT_CHANGED auto-retry to leave unlatched', () => {
    // The dangerous shape a sibling branch had: a refusal self-healing by minting a fresh request
    // key and opening a SECOND modal with no further click. It does not exist here, and this row
    // is what keeps it from being introduced unlatched later.
    const source = fs.readFileSync(
      path.resolve( __dirname, '../pages/cart.tsx' ), 'utf8' );
    expect( source ).not.toMatch( /retriedIntent/ );
    expect( source.match( /INTENT_CHANGED/g ) || [] ).toHaveLength( 0 );
  } );
} );
