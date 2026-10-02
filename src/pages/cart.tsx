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
 *   PAYMENT_INITIATION_DISABLED (200) -> INLINE, cart preserved: the server's initiation gate is
 *     off, so it stopped before the payment rail and no charge can have been made. Offers NO
 *     pay-now button. It does NOT hand off to /checkout/status/ - see NOT_PREPARED below for why
 *     that screen cannot carry this claim.
 *   PAYMENT_REQUEST_SENT (200)        -> /checkout/status/?a=<paymentAttemptId> (in-flight view).
 *     RETAINED legacy in-chat response: the server still returns it for the in-WhatsApp flow and
 *     this mapping stays until that path is migrated. See the website contract note below.
 *   payment_unavailable (409)         -> inline: no charge was made.
 *   SEND_FAILED (502)                 -> inline, with a retry: no charge was made.
 *   LINE_ITEMS_REQUIRED (400)         -> empty-cart state.
 *   UNSUPPORTED_CURRENCY / AMOUNT_NOT_SETTLED / CATALOGUE_UNAVAILABLE -> honest error copy.
 *   401                               -> session gone: back to sign-in.
 * There is NEVER a control that claims to take payment while initiation is off.
 *
 * "No charge was made" APPEARS ONLY WHERE THE SERVER HAS SAID SO. Each notice below is reached from
 * a status that means the attempt never got as far as money moving - the initiation gate was off, a
 * readiness block, a message that did not send, a request that was refused or one that never left
 * the browser. It is deliberately absent from the one path that hands off to /checkout/status/,
 * because once an attempt is in flight the browser cannot know whether the money moved, and neither
 * this page nor that one may guess.
 *
 * ADDITIVE WEBSITE RAZORPAY STANDARD CHECKOUT CONTRACT (section 8), replacing PAYMENT_REQUEST_SENT
 * for the website path without removing it for the in-chat path. The backend
 * (lambda_utils/ecommerce/website_checkout.py) returns, behind the SAME initiation gate:
 *   PAYMENT_INITIATION_DISABLED (gate off, the default) -> INLINE, cart preserved, no pay button:
 *     the gate is off, no Razorpay gateway order was created and no charge can have been made.
 *   CHECKOUT_OPTIONS_READY (gate on) -> the browser opens the Razorpay Standard Checkout hosted
 *     modal with ONLY {keyId (public), orderId (server-stored gateway order id), amountPaise
 *     (the FEAT-001 calculator total: collection+fee+GST, never the raw Wix total), currency,
 *     prefill, paymentAttemptId}. The modal's result is POSTed back to the owned backend
 *     callback, which verifies the signature over the STORED order id and STILL requires an
 *     authoritative Razorpay capture before any paid state.
 *   CHECKOUT_REJECTED -> inline, no charge was made (ownership/snapshot/intent failed).
 *   CHECKOUT_AMBIGUOUS -> hand off to /checkout/status/; the browser must not claim a charge was
 *     or was not made, exactly as the in-flight rule above requires.
 * Cart/resume data is kept until a VERIFIED_PAID finalization. "No charge was made" still appears
 * ONLY where the server has said so (the gate-off, rejected and unavailable paths), never once a
 * gateway order exists.
 *
 * CHROME AND INDEXING. Customer-session route registered in the _app.tsx isPublic chain beside
 * /checkout/status and /checkout/success; noindex; imports no Layout/Header/Footer/SupportWidget.
 * Absent from PUBLIC_PAGE_META, the sitemap and the browser route lists.
 *
 * THE TOP BAND IS SHARED. components/PageTopBand owns the main landmark, the h1, the 108px/96px
 * header clearance, the 1300px measure and the entrance animation, so this page cannot drift from
 * the fifteen routes built on RotatingHero. The band carries no price and no button: §6 of the
 * new-public-page skill puts the action further down, which is where the lime CTA sits.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import PageTopBand from '../components/PageTopBand';
import PillButton from '../components/PillButton';
import { getSession, restoreSession } from '../lib/customerAuth';
import {
  readCart, setQuantity, removeItem, toLineItems,
} from '../lib/cart';
import type { CartItem } from '../lib/cart';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const CHECKOUT_URL = `${API_BASE}/ecommerce/checkout`;
/**
 * SECTION 2 REDEMPTION ENDPOINT. The coupon/gift-card apply/remove requests go here; the SERVER
 * decides every amount (an authoritative Wix/backend discount, an authoritative gift-card balance),
 * and this page only ever RENDERS what the server returns. The browser never computes a discount or
 * a payable, and never sends an amount - it sends a code and an action, nothing more.
 */
const REDEMPTION_URL = `${API_BASE}/ecommerce/redemption`;

/** Where an unauthenticated shopper is sent, and returned from, before checkout. */
const SIGN_IN_PATH = '/account/sign-in/?return=/cart/';

/**
 * Rupees from authoritative integer paise, for DISPLAY ONLY. The server owns the arithmetic; this
 * is a presentation of a number the server already decided, never a calculation the total depends
 * on. ``₹1,214.81`` from ``121481``. Grouping is Indian (lakh/crore) via Intl.
 */
function paiseToDisplay ( paise: number ): string {
  const rupees = Math.round( paise ) / 100;
  return '₹' + rupees.toLocaleString( 'en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 } );
}

/**
 * THE OWNER-APPROVED INITIATION-FAILURE SENTENCE, verbatim, in one place.
 *
 * ITS PLACEMENT IS THE WHOLE OF ITS CORRECTNESS. It asserts that no charge was made, so it may be
 * shown only where the backend has said something that rules a charge out - the initiation gate was
 * off, readiness refused, the request was rejected, or it never left the browser. Every use below is
 * one of those. It is deliberately ABSENT from the two handoffs to /checkout/status/ and from that
 * screen entirely: once an attempt is live, "pending", "unknown" and "captured but not finalised"
 * are indistinguishable from here, and inviting a retry in any of them risks a second charge.
 *
 * A constant rather than four string literals so the claim has exactly one definition to audit, and
 * so a future edit cannot drift one copy of it onto a path that cannot support it.
 */
const NOT_PREPARED = 'We could not prepare this order. No charge was made - please try again shortly.';

/** The inline states this page can show without leaving it. Handoffs navigate instead. */
type Notice =
  | { kind: 'none' }
  | { kind: 'quiet'; message: string }
  | { kind: 'error'; message: string };

/**
 * THE SERVER-AUTHORITATIVE REDEMPTION RESPONSE, projected to the browser-safe fields only. Every
 * amount here was decided by the server; the browser renders them and never recomputes them.
 *   state                      - the backend's typed outcome the UI branches on.
 *   couponReason               - APPLIED / INVALID / EXPIRED / INELIGIBLE (coupon states).
 *   giftCardReason             - APPLIED / INVALID / EXPIRED / INELIGIBLE / INSUFFICIENT_BALANCE.
 *   discountPaise              - the authoritative coupon discount in integer paise.
 *   giftCardAppliedPaise       - the authoritative verified gift-card redemption in integer paise.
 *   remainingPayablePaise      - authoritative total - verified redemption, in integer paise.
 */
type RedemptionResponse = {
  state?: string;
  couponReason?: string;
  giftCardReason?: string;
  discountPaise?: number;
  giftCardAppliedPaise?: number;
  remainingPayablePaise?: number;
};

/** The honest copy for a gated-off / unavailable redemption surface. No provider name, ever. */
const REDEMPTION_UNAVAILABLE = 'Discounts and gift cards are not available right now.';

/** Human copy for each server-returned coupon reason. Keyed by the server's typed reason. */
const COUPON_MESSAGES: Record<string, string> = {
  INVALID: 'That coupon code is not valid.',
  EXPIRED: 'That coupon has expired.',
  INELIGIBLE: 'That coupon does not apply to the items in your cart.',
};

/** Human copy for each server-returned gift-card reason. */
const GIFT_CARD_MESSAGES: Record<string, string> = {
  INVALID: 'That gift-card code is not valid.',
  EXPIRED: 'That gift card has expired.',
  INELIGIBLE: 'That gift card cannot be used for this order.',
  INSUFFICIENT_BALANCE: 'That gift card has no balance left to use.',
};

type RedeemKind = 'coupon' | 'giftCard';

/**
 * THE COUPON + GIFT-CARD PANEL, built but honest while the backend gate is off.
 *
 * WHAT IS TRUE ABOUT IT.
 *   1. Every displayed amount - the applied discount, the applied gift-card amount, the remaining
 *      payable balance - comes from the server response, never from browser arithmetic. The server
 *      is Wix/backend-authoritative; a browser-calculated discount is never trusted.
 *   2. With the gate off / the endpoint absent / a network failure, it shows an honest unavailable
 *      state and offers no way to transact. A browser signal is never treated as proof.
 *   3. It never fetches at render/prerender time - a request happens only on an Apply/Remove click,
 *      so the static export is not broken.
 *   4. No third-party provider name appears anywhere.
 */
function RedemptionPanel (): React.ReactElement {
  const [ couponCode, setCouponCode ] = useState<string>( '' );
  const [ giftCardCode, setGiftCardCode ] = useState<string>( '' );
  const [ busy, setBusy ] = useState<RedeemKind | null>( null );
  const [ unavailable, setUnavailable ] = useState<boolean>( false );
  const [ couponApplied, setCouponApplied ] = useState<number | null>( null );
  const [ couponMessage, setCouponMessage ] = useState<string>( '' );
  const [ giftCardApplied, setGiftCardApplied ] = useState<number | null>( null );
  const [ giftCardMessage, setGiftCardMessage ] = useState<string>( '' );
  const [ remainingPayable, setRemainingPayable ] = useState<number | null>( null );

  const send = useCallback( async ( kind: RedeemKind, action: 'apply' | 'remove', code: string ): Promise<void> => {
    setBusy( kind );
    setUnavailable( false );
    try {
      // CODE + ACTION ONLY. No amount, no discount, no price leaves the browser.
      const response = await fetch( REDEMPTION_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify( { kind, action, code } ),
      } );
      if ( !response.ok ) {
        setUnavailable( true );
        return;
      }
      const data = ( await response.json().catch( () => ( {} ) ) ) as RedemptionResponse;
      const state = String( data.state || '' ).toUpperCase();

      // Gate off / rejected / ambiguous / anything unrecognised -> honest unavailable, no amounts.
      if (
        state === 'PAYMENT_INITIATION_DISABLED' || state === 'REDEMPTION_UNAVAILABLE'
        || state === 'CHECKOUT_REJECTED' || state === 'CHECKOUT_AMBIGUOUS' || state === ''
      ) {
        setUnavailable( true );
        return;
      }

      // The server-authoritative remaining payable, when the server reports one.
      if ( typeof data.remainingPayablePaise === 'number' ) {
        setRemainingPayable( data.remainingPayablePaise );
      }

      if ( kind === 'coupon' ) {
        const reason = String( data.couponReason || '' ).toUpperCase();
        if ( action === 'remove' ) {
          setCouponApplied( null );
          setCouponMessage( '' );
          return;
        }
        if ( reason === 'APPLIED' && typeof data.discountPaise === 'number' ) {
          setCouponApplied( data.discountPaise );   // server authority, never browser math
          setCouponMessage( '' );
        } else {
          setCouponApplied( null );
          setCouponMessage( COUPON_MESSAGES[ reason ] || COUPON_MESSAGES.INVALID );
        }
        return;
      }

      // gift card
      const reason = String( data.giftCardReason || '' ).toUpperCase();
      if ( action === 'remove' ) {
        setGiftCardApplied( null );
        setGiftCardMessage( '' );
        return;
      }
      if ( reason === 'APPLIED' && typeof data.giftCardAppliedPaise === 'number' ) {
        setGiftCardApplied( data.giftCardAppliedPaise );  // server authority, never browser math
        setGiftCardMessage( '' );
      } else {
        setGiftCardApplied( null );
        setGiftCardMessage( GIFT_CARD_MESSAGES[ reason ] || GIFT_CARD_MESSAGES.INVALID );
      }
    } catch {
      // A lost response cannot prove a redemption; degrade to the honest unavailable state.
      setUnavailable( true );
    } finally {
      setBusy( null );
    }
  }, [] );

  return (
    <section className="cart-redeem" aria-label="Discounts and gift cards">
      {/* COUPON */}
      <div className="cart-redeem-group">
        <label className="cart-redeem-label" htmlFor="cart-coupon">Coupon code</label>
        <div className="cart-redeem-row">
          <input
            id="cart-coupon"
            className="cart-redeem-input"
            type="text"
            autoComplete="off"
            value={ couponCode }
            onChange={ e => setCouponCode( e.target.value ) }
          />
          <button
            className="cart-redeem-apply"
            type="button"
            disabled={ busy !== null || couponCode.trim() === '' }
            onClick={ () => send( 'coupon', 'apply', couponCode.trim() ) }
          >
            { busy === 'coupon' ? 'Applying…' : 'Apply' }
          </button>
          { couponApplied !== null && (
            <button
              className="cart-redeem-remove"
              type="button"
              disabled={ busy !== null }
              onClick={ () => send( 'coupon', 'remove', '' ) }
            >
              Remove
            </button>
          ) }
        </div>
        { couponApplied !== null && (
          <p className="cart-redeem-applied" role="status" data-wc-no-translate="true">
            Applied discount: { paiseToDisplay( couponApplied ) }
          </p>
        ) }
        { couponMessage && (
          <p className="cart-redeem-msg" role="status">{ couponMessage }</p>
        ) }
      </div>

      {/* GIFT CARD */}
      <div className="cart-redeem-group">
        <label className="cart-redeem-label" htmlFor="cart-giftcard">Gift-card code</label>
        <div className="cart-redeem-row">
          <input
            id="cart-giftcard"
            className="cart-redeem-input"
            type="text"
            autoComplete="off"
            value={ giftCardCode }
            onChange={ e => setGiftCardCode( e.target.value ) }
          />
          <button
            className="cart-redeem-apply"
            type="button"
            disabled={ busy !== null || giftCardCode.trim() === '' }
            onClick={ () => send( 'giftCard', 'apply', giftCardCode.trim() ) }
          >
            { busy === 'giftCard' ? 'Applying…' : 'Apply' }
          </button>
          { giftCardApplied !== null && (
            <button
              className="cart-redeem-remove"
              type="button"
              disabled={ busy !== null }
              onClick={ () => send( 'giftCard', 'remove', '' ) }
            >
              Remove
            </button>
          ) }
        </div>
        { giftCardApplied !== null && (
          <p className="cart-redeem-applied" role="status" data-wc-no-translate="true">
            Applied gift card: { paiseToDisplay( giftCardApplied ) }
          </p>
        ) }
        { giftCardApplied !== null && remainingPayable !== null && (
          <p className="cart-redeem-remaining" role="status" data-wc-no-translate="true">
            Remaining payable balance: { paiseToDisplay( remainingPayable ) }
          </p>
        ) }
        { giftCardMessage && (
          <p className="cart-redeem-msg" role="status">{ giftCardMessage }</p>
        ) }
      </div>

      { unavailable && (
        <p className="cart-redeem-off" role="status" data-phase="unavailable">
          { REDEMPTION_UNAVAILABLE }
        </p>
      ) }

      <style jsx>{`
        .cart-redeem{margin:28px 0 0;padding:20px 0 0;border-block-start:1px solid #e5e7eb}
        .cart-redeem-group{margin:0 0 20px}
        .cart-redeem-group:last-of-type{margin-bottom:0}
        .cart-redeem-label{display:block;font-size:14px;font-weight:700;color:#1a3a2a;margin:0 0 8px}
        .cart-redeem-row{display:flex;align-items:center;gap:12px;flex-wrap:wrap}
        .cart-redeem-input{
          flex:1 1 220px;min-height:44px;padding:0 12px;border:1px solid #e5e7eb;border-radius:8px;
          font-family:inherit;font-size:16px;color:#1a1a1a;
        }
        .cart-redeem-input:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
        /* The apply control takes the site's lime, like the main CTA but at the secondary rung. */
        .cart-redeem-apply{
          display:inline-flex;align-items:center;justify-content:center;min-height:44px;
          padding:0 20px;border:2px solid #1a3a2a;border-radius:50px;background:#d1f470;
          color:#1a3a2a;font-family:inherit;font-size:16px;font-weight:600;cursor:pointer;
          transition:background-color .2s;
        }
        .cart-redeem-apply:hover:not(:disabled){background:#fff}
        .cart-redeem-apply:focus-visible{outline:3px solid #1a3a2a;outline-offset:3px}
        .cart-redeem-apply:disabled{opacity:.6;cursor:default}
        .cart-redeem-remove{
          display:inline-flex;align-items:center;min-height:44px;padding-inline:8px;border:none;
          background:none;color:#1a3a2a;font-family:inherit;font-size:16px;font-weight:700;
          cursor:pointer;text-decoration:underline;text-underline-offset:3px;
        }
        .cart-redeem-remove:hover{background:rgba(209,244,112,.22);border-radius:8px}
        .cart-redeem-remove:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px;border-radius:2px}
        .cart-redeem-remove:disabled{opacity:.6;cursor:default}
        .cart-redeem-applied,.cart-redeem-remaining{
          margin:10px 0 0;font-size:16px;font-weight:700;color:#1a3a2a;
          font-variant-numeric:tabular-nums;
        }
        .cart-redeem-remaining{color:#1a1a1a}
        .cart-redeem-msg{
          margin:10px 0 0;padding:12px 14px;border-radius:10px;background:rgba(209,244,112,.22);
          border-inline-start:3px solid #d1f470;font-size:16px;line-height:1.5;color:#1a3a2a;
        }
        .cart-redeem-off{
          margin:16px 0 0;padding:12px 14px;border-radius:10px;background:rgba(209,244,112,.22);
          border-inline-start:3px solid #d1f470;font-size:16px;line-height:1.5;color:#1a3a2a;
        }
      `}</style>
    </section>
  );
}

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
    let session;
    try { session = getSession() || await restoreSession(); }
    catch {
      setNotice( { kind: 'quiet', message: 'Sign-in is temporarily unavailable. Please try again.' } );
      return;
    }
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

      // PAYMENT_REQUEST_SENT hands off to the hosted status screen, which owns the honest copy for
      // an attempt that is genuinely in flight. NO claim about a charge is made here in either
      // direction: the request has left and only the server knows where it stands.
      if ( status === 'PAYMENT_REQUEST_SENT' && data.paymentAttemptId )
      {
        // Keep the cart until the server confirms a paid order.
        const a = encodeURIComponent( String( data.paymentAttemptId ) );
        window.location.assign( `/checkout/status/?a=${a}` );
        return;
      }

      // PAYMENT_INITIATION_DISABLED IS ANSWERED HERE, NOT ON THE STATUS SCREEN, and both halves of
      // that are deliberate.
      //
      // WHY IT STAYS ON THIS PAGE. This status means the server's own initiation gate is off, so it
      // stopped before the payment rail: there is backend evidence that nothing reached a provider,
      // which is exactly the condition the approved sentence requires. The status screen cannot
      // carry that sentence, because its viewFor() folds this status in with "we cannot find this
      // attempt" and anything unrecognised - states where the money may in fact have moved - and a
      // claim of no charge is the one wrong answer that cannot be taken back. Keeping the sentence
      // on the page that received the response keeps it pinned to the evidence for it.
      //
      // WHY THE CART SURVIVES. It used to be cleared here, alongside the in-flight case. That was
      // wrong twice over: a disabled gate leaves the shopper nothing to come back to, and the
      // notice below renders inside the items list, so clearing the cart would have replaced the
      // explanation with "Your cart is empty." The attempt the server recorded is not payable, so
      // the cart is still the shopper's.
      if ( status === 'PAYMENT_INITIATION_DISABLED' )
      {
        setNotice( { kind: 'quiet', message: NOT_PREPARED } );
        return;
      }

      // 409 readiness-blocked. The server refused before reaching the payment rail, so the same
      // evidence holds and the same sentence is the honest one.
      if ( status === 'PAYMENT_UNAVAILABLE' )
      {
        setNotice( { kind: 'quiet', message: NOT_PREPARED } );
        return;
      }

      // Empty cart per the server: reflect the empty state.
      if ( status === 'LINE_ITEMS_REQUIRED' )
      {
        setItems( readCart() );
        return;
      }

      // The message did not go out. The attempt exists and nothing was charged, so a retry is safe.
      if ( status === 'SEND_FAILED' )
      {
        setNotice( {
          kind: 'quiet',
          message: 'We could not open the payment. No charge was made - please try again.',
        } );
        return;
      }

      // Priced/currency/catalogue problems, or any other non-OK. The request was refused, so
      // nothing was charged.
      if (
        status === 'UNSUPPORTED_CURRENCY' || status === 'AMOUNT_NOT_SETTLED'
        || status === 'CATALOGUE_UNAVAILABLE'
      )
      {
        setNotice( { kind: 'error', message: NOT_PREPARED } );
        return;
      }

      // Anything unrecognised: fail honestly rather than implying success. Safe to claim no charge
      // because this branch is reached only when the response carried NO attempt handed off above -
      // i.e. the server did not report a live attempt, so there is nothing in flight to be wrong
      // about.
      setNotice( { kind: 'error', message: 'We could not confirm checkout. Check your orders before trying again.' } );
    }
    catch
    {
      // A lost response cannot prove that the request never reached the server.
      setNotice( {
        kind: 'error',
        message: 'We could not confirm checkout. Check your orders before trying again.',
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
      <PageTopBand
        heading="Your cart"
        sub="Review what you have added before you check out."
        ariaLabel="Your cart"
      >
        <div className="cart-in">
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

              {/* Coupon + gift card. Every amount shown is server-authoritative; with the backend
                  gate off this shows an honest unavailable state and cannot transact. */}
              <RedemptionPanel />

              {/* Catalogue prices are for display; the server approves the payable total. */}
              <p className="cart-note">
                The store confirms your final total, including taxes and fees, before payment.
              </p>

              {/* role is chosen by severity, not by colour: 'status' is polite for a state the
                  shopper can simply retry, 'alert' interrupts for one they cannot. Neither relies
                  on the tint to carry the meaning - the sentence does. */}
              {notice.kind === 'quiet' && (
                <p className="cart-status" role="status">{ notice.message }</p>
              )}
              {notice.kind === 'error' && (
                <p className="cart-status cart-status-firm" role="alert">{ notice.message }</p>
              )}

              {/* THE SAME TWO-SEGMENT PILL as the sign-in CTA (PillButton), because this button is
                  the customer login gate: an anonymous shopper who clicks it is sent to
                  /account/sign-in. Never a "pay now" claim. The visible pill reads
                  "Checkout | Proceed" and its accessible name is now that same visible text,
                  "Checkout Proceed".

                  IT USED TO PASS ariaLabel="Proceed to checkout", which read better but was a
                  WCAG 2.5.3 Label in Name failure: the name did not contain the visible text, so
                  a speech-input user saying "click Checkout" or "click Proceed" hit nothing. The
                  prop no longer exists - see PillButton's docblock. Visible text is unchanged;
                  only the accessible name moved. Real type="button" running proceed(), disabled
                  while busy. */}
              <div className="cart-pill">
                <PillButton
                  as="button"
                  type="button"
                  label="Checkout"
                  action={ busy ? 'Preparing…' : 'Proceed' }
                  onClick={ proceed }
                  disabled={ busy }
                  busy={ busy }
                />
              </div>

              <p className="cart-back"><Link href="/shop/">Keep shopping</Link></p>
            </>
          )}
        </div>

        <style jsx>{`
          /* NO TOP PADDING, NO MEASURE AND NO FONT STACK HERE: PageTopBand owns all three, the
             way .shop-shell records for RotatingHero. This div sits inside .ptb-layout, which has
             already applied the 108px/96px header clearance, the 1300px measure and the gutter.
             820px is the reading measure for a list of lines plus a paragraph of terms - the band
             above it is wider, which is the same relationship .rh-sub has to .rh-head. */
          .cart-in{width:100%;max-width:820px;margin:0}
          /* The body rung: 20px/400/1.4/-.125px at rgba(0,0,0,.898). It was 18px at .7 alpha,
             which is neither of the two rungs this site has. */
          .cart-body{
            font-size:20px;font-weight:400;line-height:1.4;letter-spacing:-.125px;
            color:rgba(0,0,0,.898);margin:0;
          }
          .cart-empty{margin:0}
          .cart-list{list-style:none;margin:0;padding:0}
          /* 1px #e5e7eb is the static hairline, per the rule that 1px is a static edge and 2px a
             hoverable one. Logical block-end so a mirrored document keeps the rule under the row. */
          .cart-row{
            display:flex;justify-content:space-between;align-items:center;gap:24px;
            padding-block:20px;border-block-end:1px solid #e5e7eb;flex-wrap:wrap;
          }
          .cart-row-main{min-width:0}
          /* The card-heading rung: 22px/700/lh1.27/-.25px, the same three numbers as .shop-name
             and .shopd-price, which is what makes the cart read as the same site as the catalogue.
             It was 20px/600, a rung that exists nowhere else. */
          .cart-name{font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;margin:0 0 8px}
          /* EVERY LINK RULE GOES THROUGH :global(). styled-jsx adds its scoping class only to
             lowercase DOM tags it can see in this file, never to a capitalised component, so the
             compiled rule for a next/link child would match nothing. */
          .cart-name :global(a){color:#000;text-decoration:none;text-underline-offset:3px}
          .cart-name :global(a:hover){color:#1a3a2a}
          .cart-name :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
          /* Price in dark green, never lime: lime means actionable and the page's one lime surface
             is the button below. #1a3a2a on white is about 11:1. Tabular figures so a column of
             prices lines up on the decimal. */
          .cart-price{
            font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
            color:#1a3a2a;margin:0;font-variant-numeric:tabular-nums;
          }
          .cart-row-controls{display:flex;align-items:center;gap:12px}
          .cart-qty-label{font-size:14px;font-weight:700;color:#1a3a2a}
          /* 44px is the tap-target floor. The site's CTA is 52px; a secondary field is not
             required to match it, only to clear 44. */
          .cart-qty{
            width:72px;min-height:44px;padding:0 10px;border:1px solid #e5e7eb;border-radius:8px;
            font-family:inherit;font-size:16px;text-align:center;color:#1a1a1a;
          }
          .cart-qty:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px}
          /* A 44px target, not a 27px one. This was padding:6px around a 15px line, which
             computed to about 27px tall - under the floor devicecheck enforces elsewhere on the
             site and the smallest control on the page. */
          .cart-remove{
            display:inline-flex;align-items:center;min-height:44px;padding-inline:8px;
            border:none;background:none;color:#1a3a2a;font-family:inherit;font-size:16px;
            font-weight:700;cursor:pointer;text-decoration:underline;text-underline-offset:3px;
          }
          .cart-remove:hover{background:rgba(209,244,112,.22);border-radius:8px}
          .cart-remove:focus-visible{outline:3px solid #1a3a2a;outline-offset:2px;border-radius:2px}
          /* The terms box takes the catalogue's own notice treatment - 1px #e5e7eb hairline,
             12px radius, the dim rung at rgba(0,0,0,.54) - so it reads as the same kind of aside
             .shopd-note and .shop-asof are. */
          .cart-note{
            margin:28px 0 0;padding:16px 18px;border:1px solid #e5e7eb;border-radius:12px;
            font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }

          /* NO RED, ON OWNER INSTRUCTION, AND THE PALETTE HAS A BETTER ANSWER ANYWAY.
             This was #fbe9e9 on a #f0c0c0 border with #8a1f1f text - three colours that appear
             nowhere in the home design, on a site whose only red is the single full stop in the
             wordmark. The replacement is the lime state tint rgba(209,244,112,.22) behind a solid
             #d1f470 inline-start edge with #1a3a2a type, which is exactly the treatment
             .shop-asof and .blog-degraded already use for "read this before you trust what is
             below it". #1a3a2a on the composited tint measures about 10:1.
             COLOUR IS NOT THE ONLY CUE, which is what makes dropping red safe rather than a
             regression: the sentence states the problem, and role=status / role=alert carries the
             severity to assistive technology. The firmer variant thickens the edge to 4px and goes
             to weight 700 rather than changing hue - a luminance and weight step, which survives
             forced-colors and reduced colour discrimination in a way a hue swap does not.
             border-inline-start, not border-left, so the edge follows the reading direction. */
          .cart-status{
            margin:20px 0 0;padding:14px 16px;border-radius:10px;
            background:rgba(209,244,112,.22);border-inline-start:3px solid #d1f470;
            font-size:16px;line-height:1.5;color:#1a3a2a;
          }
          .cart-status-firm{border-inline-start-width:4px;font-weight:700}

          /* THE CHECKOUT/LOGIN CTA IS NOW PillButton, the home-page two-segment pill, so this page
             no longer carries a .cart-cta rule: the component owns the pill's shape, colours, focus
             ring, hover lift and reduced-motion handling. It replaced the single lime surface on
             owner instruction, to make the login gate the dark-green + mint pill. There is 28px of
             space above it, applied by the pill's own container margin via .cart-pill below. */
          .cart-pill{margin-top:28px}
          /* 44px, so the way back off this page is a real target too. */
          .cart-back{margin:28px 0 0;font-size:16px;line-height:1.55}
          .cart-back :global(a){
            display:inline-flex;align-items:center;min-height:44px;
            color:#1a3a2a;font-weight:700;text-underline-offset:3px;
          }
          .cart-back :global(a:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px;border-radius:2px}
          @media(max-width:767px){
            .cart-body{font-size:18px}
            .cart-row{gap:16px}
          }
          /* The CTA's reduced-motion handling moved into PillButton with the button itself. */
        `}</style>
      </PageTopBand>
    </>
  );
}
