/**
 * /cart/ - the cart review page and the checkout `create` handoff.
 *
 * WHAT IT DOES. Lists the cart (name + Wix formattedPrice for DISPLAY only), lets the shopper
 * change quantities or remove lines, and on "Proceed to checkout" ensures a customer session then
 * POSTs {action:'create', lineItems} to {NEXT_PUBLIC_API_BASE}/ecommerce/checkout with a
 * Authorization: Bearer token from getSession(). The lineItems carry catalogue references and
 * quantities ONLY (src/lib/cart.ts, toLineItems) - the browser never sends a price.
 *
 * THE AUTH GATE. The checkout create endpoint requires an authenticated customer
 * (customer_auth.require_customer). If getSession() is null the shopper is sent to
 * /account/sign-in/?return=/cart/ FIRST and returned here afterwards; the cart is in localStorage
 * so it survives the redirect. A signed-in shopper proceeds directly. A test asserts that a null
 * session routes to sign-in and makes NO create call.
 *
 * TRUTHFUL RESPONSE HANDLING - the honesty requirement. The create responses are mapped exactly as
 * checkout/handler.py documents them:
 *   PAYMENT_INITIATION_DISABLED (200) -> hand off to the hosted status screen
 *     /checkout/status/?a=<paymentAttemptId>, whose viewFor() already maps this status to the
 *     neutral 'unavailable' view: "checkout prepared, live payment not being accepted yet". This
 *     NEVER implies a charge and offers NO pay-now button. We reuse the hosted screen rather than
 *     duplicating it.
 *   PAYMENT_REQUEST_SENT (200)        -> /checkout/status/?a=<paymentAttemptId> (in-flight view).
 *   payment_unavailable (409)         -> honest inline copy: "no charge was made".
 *   SEND_FAILED (502)                 -> honest inline copy with a retry, no charge.
 *   LINE_ITEMS_REQUIRED (400)         -> empty-cart state.
 *   UNSUPPORTED_CURRENCY / AMOUNT_NOT_SETTLED / CATALOGUE_UNAVAILABLE -> honest error copy.
 *   401                               -> session gone: back to sign-in.
 * There is NEVER a control that claims to take payment while initiation is off.
 *
 * CHROME AND INDEXING. Customer-session route registered in the _app.tsx isPublic chain beside
 * /checkout/status and /checkout/success; noindex; imports no Layout/Header/Footer/SupportWidget.
 * Absent from PUBLIC_PAGE_META, the sitemap and the browser route lists.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import { getSession } from '../lib/customerAuth';
import {
  readCart, setQuantity, removeItem, clearCart, toLineItems,
} from '../lib/cart';
import type { CartItem } from '../lib/cart';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const CHECKOUT_URL = `${API_BASE}/ecommerce/checkout`;

/** Where an unauthenticated shopper is sent, and returned from, before checkout. */
const SIGN_IN_PATH = '/account/sign-in/?return=/cart/';

/** The inline states this page can show without leaving it. Handoffs navigate instead. */
type Notice =
  | { kind: 'none' }
  | { kind: 'unavailable'; message: string }
  | { kind: 'send-failed'; message: string }
  | { kind: 'error'; message: string };

export default function Cart (): React.ReactElement {
  const [ items, setItems ] = useState<CartItem[]>( [] );
  const [ ready, setReady ] = useState<boolean>( false );
  const [ busy, setBusy ] = useState<boolean>( false );
  const [ notice, setNotice ] = useState<Notice>( { kind: 'none' } );

  useEffect( () => {
    setItems( readCart() );
    setReady( true );
  }, [] );

  const changeQuantity = useCallback( ( ref: string, quantity: number ): void => {
    setItems( setQuantity( ref, quantity ) );
  }, [] );

  const drop = useCallback( ( ref: string ): void => {
    setItems( removeItem( ref ) );
  }, [] );

  const proceed = useCallback( async (): Promise<void> => {
    setNotice( { kind: 'none' } );

    // AUTH GATE. No session -> sign-in first, cart preserved in localStorage. No create call.
    const session = getSession();
    if ( !session )
    {
      window.location.assign( SIGN_IN_PATH );
      return;
    }

    const lineItems = toLineItems();
    if ( lineItems.length === 0 )
    {
      setItems( readCart() );
      return;
    }

    setBusy( true );
    try
    {
      const response = await fetch( CHECKOUT_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.accessToken}`,
        },
        // refs + quantities ONLY. No price, amount or currency leaves the browser.
        body: JSON.stringify( { action: 'create', lineItems } ),
      } );

      if ( response.status === 401 )
      {
        // Session gone or invalid: sign in again.
        window.location.assign( SIGN_IN_PATH );
        return;
      }

      const data = ( await response.json().catch( () => ( {} ) ) ) as {
        status?: string;
        error?: string;
        paymentAttemptId?: string;
        message?: string;
      };
      const status = String( data.status || data.error || '' ).toUpperCase();

      // PAYMENT_INITIATION_DISABLED and PAYMENT_REQUEST_SENT both hand off to the hosted status
      // screen, which owns the honest copy for each. The disabled status resolves to the neutral
      // 'unavailable' view there - prepared, not charged, no pay button.
      if (
        ( status === 'PAYMENT_INITIATION_DISABLED' || status === 'PAYMENT_REQUEST_SENT' )
        && data.paymentAttemptId
      )
      {
        // The cart has been turned into a prepared attempt; it should not be re-submitted.
        clearCart();
        const a = encodeURIComponent( String( data.paymentAttemptId ) );
        window.location.assign( `/checkout/status/?a=${a}` );
        return;
      }

      // 409 readiness-blocked: honest, non-alarming, and explicit that nothing was charged.
      if ( status === 'PAYMENT_UNAVAILABLE' )
      {
        setNotice( {
          kind: 'unavailable',
          message: 'Payments are temporarily unavailable. No charge was made.',
        } );
        return;
      }

      // Empty cart per the server: reflect the empty state.
      if ( status === 'LINE_ITEMS_REQUIRED' )
      {
        setItems( readCart() );
        return;
      }

      // The message did not go out; the attempt exists and nothing was charged. Offer a retry.
      if ( status === 'SEND_FAILED' )
      {
        setNotice( {
          kind: 'send-failed',
          message: 'We could not open the payment. No charge was made - please try again.',
        } );
        return;
      }

      // Priced/currency/catalogue problems, or any other non-OK: honest error copy, no charge.
      if (
        status === 'UNSUPPORTED_CURRENCY' || status === 'AMOUNT_NOT_SETTLED'
        || status === 'CATALOGUE_UNAVAILABLE' || !response.ok
      )
      {
        setNotice( {
          kind: 'error',
          message: 'We could not prepare this order. No charge was made - please try again shortly.',
        } );
        return;
      }

      // Anything unrecognised: fail honestly rather than implying success.
      setNotice( {
        kind: 'error',
        message: 'We could not prepare this order. No charge was made - please try again shortly.',
      } );
    }
    catch
    {
      setNotice( {
        kind: 'error',
        message: 'We could not reach the store. No charge was made - please try again.',
      } );
    }
    finally
    {
      setBusy( false );
    }
  }, [] );

  const isEmpty = ready && items.length === 0;

  return (
    <>
      <Head>
        <title>Your cart — WECARE.DIGITAL</title>
        {/* Customer-session, per-person: never indexed. */}
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <main className="cart-wrap" aria-label="Your cart">
        <div className="cart-in">
          <h1 className="cart-h1">Your cart</h1>

          {!ready && <p className="cart-body">Loading your cart…</p>}

          {isEmpty && (
            <div className="cart-empty">
              <p className="cart-body">Your cart is empty.</p>
              <p className="cart-back"><Link href="/shop/">Browse the shop</Link></p>
            </div>
          )}

          {ready && items.length > 0 && (
            <>
              <ul className="cart-list">
                { items.map( item => (
                  <li className="cart-row" key={ item.ref }>
                    <div className="cart-row-main">
                      <p className="cart-name">
                        { item.slug
                          ? <Link href={ `/shop/${item.slug}/` }>{ item.name }</Link>
                          : item.name }
                      </p>
                      {/* DISPLAY ONLY. This Wix passthrough price never reaches the server. */}
                      <p className="cart-price" data-wc-no-translate="true">{ item.formattedPrice }</p>
                    </div>
                    <div className="cart-row-controls">
                      <label className="cart-qty-label" htmlFor={ `qty-${item.ref}` }>Qty</label>
                      <input
                        id={ `qty-${item.ref}` }
                        className="cart-qty"
                        type="number"
                        min={ 1 }
                        value={ item.quantity }
                        onChange={ e => changeQuantity( item.ref, Number( e.target.value ) ) }
                      />
                      <button
                        className="cart-remove"
                        type="button"
                        onClick={ () => drop( item.ref ) }
                        aria-label={ `Remove ${item.name}` }
                      >
                        Remove
                      </button>
                    </div>
                  </li>
                ) ) }
              </ul>

              {/* THE HONEST BOUNDARY. The final amount is computed and confirmed server-side; this
                  page shows reference prices only and says so. Payment initiation is off by
                  default, so proceeding prepares the order without taking money - and never
                  presents a control that claims to. */}
              <p className="cart-note">
                Prices shown are read from the store catalogue for reference. The amount is
                confirmed by the store when you proceed. Live payment is not being accepted yet, so
                proceeding prepares your order without charging you - nothing is taken here.
              </p>

              {notice.kind === 'unavailable' && (
                <p className="cart-status cart-status-quiet" role="status">{ notice.message }</p>
              )}
              {notice.kind === 'send-failed' && (
                <p className="cart-status cart-status-quiet" role="status">{ notice.message }</p>
              )}
              {notice.kind === 'error' && (
                <p className="cart-status cart-status-error" role="alert">{ notice.message }</p>
              )}

              {/* The single LIME actionable surface on this page. Never a "pay now" claim. */}
              <button className="cart-cta" type="button" onClick={ proceed } disabled={ busy }>
                { busy ? 'Preparing…' : 'Proceed to checkout' }
              </button>

              <p className="cart-back"><Link href="/shop/">Keep shopping</Link></p>
            </>
          )}
        </div>

        <style jsx>{`
          .cart-wrap{
            min-height:calc(100vh - 69px);
            padding-top:108px;box-sizing:border-box;background:#fff;
            font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;
            color:#1a1a1a;
          }
          .cart-in{width:100%;max-width:820px;margin:0 auto;padding:48px 24px 96px;box-sizing:border-box}
          .cart-h1{
            font-size:clamp(32px,4.3vw,52px);font-weight:600;line-height:1.06;
            letter-spacing:-0.04em;color:rgba(0,0,0,.95);margin:0 0 28px;
          }
          .cart-body{font-size:18px;line-height:1.5;color:rgba(0,0,0,.7);margin:0}
          .cart-empty{margin-top:12px}
          .cart-list{list-style:none;margin:0;padding:0}
          .cart-row{
            display:flex;justify-content:space-between;align-items:center;gap:24px;
            padding:20px 0;border-bottom:1px solid #e5e7eb;flex-wrap:wrap;
          }
          .cart-row-main{min-width:0}
          .cart-name{font-size:20px;font-weight:600;line-height:1.3;margin:0 0 6px}
          .cart-name :global(a){color:#000;text-decoration:none;text-underline-offset:3px}
          .cart-name :global(a:hover){color:#1a3a2a}
          .cart-name :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
          /* Price is dark green, never lime - lime is reserved for the one CTA. */
          .cart-price{
            font-size:18px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
            color:#1a3a2a;margin:0;font-variant-numeric:tabular-nums;
          }
          .cart-row-controls{display:flex;align-items:center;gap:12px}
          .cart-qty-label{font-size:14px;font-weight:600;color:#1a3a2a}
          .cart-qty{
            width:64px;min-height:44px;padding:0 10px;border:1px solid #e5e7eb;border-radius:8px;
            font-size:16px;text-align:center;
          }
          .cart-qty:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
          .cart-remove{
            border:none;background:none;color:rgba(0,0,0,.54);font-size:15px;font-weight:600;
            cursor:pointer;text-decoration:underline;text-underline-offset:3px;padding:6px;
          }
          .cart-remove:hover{color:#1a3a2a}
          .cart-remove:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px;border-radius:2px}
          .cart-note{
            margin:28px 0 0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }
          .cart-status{margin:20px 0 0;padding:14px 16px;border-radius:10px;font-size:15px;line-height:1.5}
          .cart-status-quiet{background:rgba(0,0,0,.05);color:rgba(0,0,0,.7)}
          .cart-status-error{background:#fbe9e9;border:1px solid #f0c0c0;color:#8a1f1f}
          /* .shopd-cta's lime treatment: the single actionable surface, #1a3a2a text, 2px border. */
          .cart-cta{
            display:inline-flex;align-items:center;justify-content:center;min-height:52px;
            margin-top:28px;padding:0 26px;border:2px solid #d1f470;border-radius:50px;
            background:#d1f470;color:#1a3a2a;font-size:17px;font-weight:600;cursor:pointer;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .cart-cta:hover:not(:disabled){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          .cart-cta:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
          .cart-cta:disabled{opacity:.6;cursor:default}
          .cart-back{margin:28px 0 0;font-size:16px;line-height:1.55}
          .cart-back :global(a){color:#1a3a2a;font-weight:600;text-underline-offset:3px}
          .cart-back :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
          @media(max-width:767px){
            .cart-wrap{min-height:calc(100vh - 85px);padding-top:96px}
            .cart-in{padding:32px 16px 64px}
          }
          @media(prefers-reduced-motion:reduce){
            .cart-cta{transition:none}
            .cart-cta:hover:not(:disabled){transform:none;box-shadow:none}
          }
        `}</style>
      </main>
    </>
  );
}
