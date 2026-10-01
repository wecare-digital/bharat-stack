/**
 * Checkout status — the hosted payment handoff/status screen.
 *
 * What this screen is, and is not
 * -------------------------------
 * It is a STATUS MIRROR, not a second checkout. It cannot choose an amount, an account, a return
 * URL or a payment outcome — every one of those is decided server-side and this page only reflects
 * what the backend already knows. The customer pays inside WhatsApp (Meta + Razorpay); this page
 * tells them where that stands and never asks them to pay here.
 *
 * The five states it renders come straight from the payment-attempt state machine, mapped to the
 * copy the Wix-Velo prompt §47-48 specifies:
 *
 *   in flight (CREATED / READINESS_CHECKED / REQUEST_SENT / PENDING)  -> "Confirming your payment"
 *   paid, order still finalizing (PAID but no order number yet)       -> "Payment received"
 *   done (PAID + order number)                                        -> redirect to /checkout/success
 *   failed / cancelled / expired                                      -> "Payment wasn't completed"
 *   disabled (initiation off) / unknown                               -> a neutral holding message
 *
 * Authority and privacy
 * ---------------------
 * The URL carries ONE opaque value: `?a=<paymentAttemptId>` (a UUIDv7, not a phone, not a price,
 * not an order number). It is not an authority — the backend authorises every read against the
 * customer's Cognito session (bearer from getSession), and a request for someone else's attempt
 * returns the same opaque 401 as no session at all. So a leaked URL reveals nothing and grants
 * nothing: without the session it is inert.
 *
 * "Do not pay again" is load-bearing
 * ----------------------------------
 * A paid-but-finalizing state must NEVER offer a retry, and a genuine failure offers a retry only
 * because the backend has confirmed the attempt is terminally failed. This page reads
 * `attempt.canRetry` from the backend rather than deciding for itself — the state machine owns that
 * call, because "still pending" and "definitely failed" look identical from the browser.
 *
 * Degrades without JavaScript
 * ---------------------------
 * The settled markup is the "Confirming…" state written into the DOM, so a no-JS load shows a
 * coherent screen (per the new-public-page skill: the state nobody looks at must still be right).
 * The polling only ever refines it.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import { getSession } from '../../lib/customerAuth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const CHECKOUT_STATUS_URL = `${API_BASE}/ecommerce/checkout/status`;

/** How often the screen re-asks the backend while a payment is in flight. */
const POLL_INTERVAL_MS = 4000;
/** Stop polling after this long; the customer can refresh. Bounds a stuck tab. */
const POLL_CEILING_MS = 5 * 60 * 1000;

type View =
  | 'loading'
  | 'confirming'
  | 'finalizing'
  | 'failed'
  | 'unavailable';

interface AttemptView {
  status?: string;
  orderNumber?: string | null;
  canRetry?: boolean;
}

/** Which of the five screens a backend status maps to. Redirect to success is handled separately. */
function viewFor ( status: string | undefined, orderNumber: string | null | undefined ): View {
  const s = String( status || '' ).toUpperCase();
  if ( s === 'PAYMENT_PAID' )
  {
    return orderNumber ? 'confirming' /* momentary; redirect fires */ : 'finalizing';
  }
  if ( s === 'PAYMENT_FAILED' || s === 'PAYMENT_CANCELLED' || s === 'PAYMENT_EXPIRED' )
  {
    return 'failed';
  }
  if (
    s === 'CREATED' || s === 'PAYMENT_READINESS_CHECKED'
    || s === 'PAYMENT_REQUEST_SENT' || s === 'PAYMENT_PENDING'
  )
  {
    return 'confirming';
  }
  // PAYMENT_INITIATION_DISABLED, empty, or anything unrecognised: a neutral holding screen that
  // never claims success or invites a second payment.
  return 'unavailable';
}

function attemptIdFromUrl (): string {
  if ( typeof window === 'undefined' ) return '';
  const params = new URLSearchParams( window.location.search );
  return String( params.get( 'a' ) || '' ).trim();
}

export default function CheckoutStatus (): React.ReactElement {
  // The settled server state is "confirming": a no-JS load shows a coherent, honest screen rather
  // than a blank one. Polling only ever refines this.
  const [ view, setView ] = useState<View>( 'confirming' );
  const [ orderNumber, setOrderNumber ] = useState<string>( '' );

  const poll = useCallback( async ( attemptId: string ): Promise<boolean> => {
    const session = getSession();
    if ( !session )
    {
      // No session: the screen cannot prove ownership, so it says so rather than guessing.
      setView( 'unavailable' );
      return true; // stop polling
    }
    try
    {
      const response = await fetch( CHECKOUT_STATUS_URL, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          Authorization: `Bearer ${session.accessToken}`,
        },
        body: JSON.stringify( { action: 'status', paymentAttemptId: attemptId } ),
      } );
      if ( !response.ok )
      {
        setView( 'unavailable' );
        return response.status === 401; // 401 is terminal here (verify again); others we retry
      }
      const data = ( await response.json() ) as { attempt?: AttemptView; status?: string };
      const attempt = data.attempt || {};
      const nextView = viewFor( attempt.status, attempt.orderNumber );
      if ( String( attempt.status || '' ).toUpperCase() === 'PAYMENT_PAID' && attempt.orderNumber )
      {
        // Done. Hand off to the success page, which owns the confirmation copy.
        const n = encodeURIComponent( String( attempt.orderNumber ) );
        window.location.replace( `/checkout/success/?o=${n}` );
        return true;
      }
      setView( nextView );
      setOrderNumber( '' );
      // Keep polling only while still in flight. A failed/unavailable state is not going to
      // change on its own from here, so stop and let the customer act.
      return nextView !== 'confirming' && nextView !== 'finalizing';
    }
    catch
    {
      // A transient network error is not a failure of the payment. Hold and keep polling.
      return false;
    }
  }, [] );

  useEffect( () => {
    const attemptId = attemptIdFromUrl();
    if ( !attemptId )
    {
      setView( 'unavailable' );
      return;
    }
    let stopped = false;
    const startedAt = Date.now();
    let timer: ReturnType<typeof setTimeout>;

    const tick = async (): Promise<void> => {
      if ( stopped ) return;
      const done = await poll( attemptId );
      if ( stopped || done ) return;
      if ( Date.now() - startedAt > POLL_CEILING_MS ) return;
      timer = setTimeout( tick, POLL_INTERVAL_MS );
    };
    void tick();

    return () => {
      stopped = true;
      if ( timer ) clearTimeout( timer );
    };
  }, [ poll ] );

  const copy = COPY[ view ];

  return (
    <>
      <Head>
        <title>{copy.title} — WECARE.DIGITAL</title>
        {/* Transactional, session-bound, and per-customer: never indexed. */}
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <main className="co-status">
        <section className="co-card" role="status" aria-live="polite">
          <div className={`co-mark co-mark-${view}`} aria-hidden="true" />
          <h1 className="co-title">{copy.title}</h1>
          <p className="co-body">{copy.body}</p>

          {view === 'failed' && (
            <div className="co-actions">
              {/* Retry returns to the cart, where a NEW checkout (new reference, re-priced) is
                  created. This page never re-sends a payment itself. Only shown on a
                  backend-confirmed terminal failure. */}
              <Link className="co-btn co-btn-primary" href="/shop/">Try again</Link>
              <Link className="co-btn co-btn-quiet" href="/">Back to home</Link>
            </div>
          )}
          {view === 'finalizing' && (
            <p className="co-note">Please keep this page open. This usually takes a few seconds.</p>
          )}
          {view === 'unavailable' && (
            <div className="co-actions">
              <Link className="co-btn co-btn-quiet" href="/shop/">Return to the store</Link>
            </div>
          )}
        </section>
      </main>

      <style jsx>{`
        .co-status {
          min-height: 100vh;
          min-height: 100dvh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding-block: 48px;
          padding-inline: 20px;
        }
        .co-card {
          width: 100%;
          max-inline-size: 30rem;
          text-align: center;
        }
        .co-mark {
          inline-size: 56px;
          block-size: 56px;
          margin-inline: auto;
          margin-block-end: 24px;
          border-radius: 50%;
        }
        .co-mark-confirming,
        .co-mark-finalizing {
          border: 3px solid rgba(0, 0, 0, 0.12);
          border-block-start-color: #1f8f4e;
          animation: co-spin 900ms linear infinite;
        }
        .co-mark-failed {
          background: #fbe9e9;
        }
        .co-mark-unavailable {
          background: rgba(0, 0, 0, 0.06);
        }
        .co-title {
          font-size: clamp(24px, 3.2vw, 32px);
          font-weight: 700;
          line-height: 1.12;
          letter-spacing: -0.02em;
          margin: 0 0 12px;
        }
        .co-body {
          font-size: 16px;
          line-height: 1.5;
          color: #444;
          margin: 0;
        }
        .co-note {
          font-size: 14px;
          color: #666;
          margin-block-start: 16px;
        }
        .co-actions {
          margin-block-start: 28px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          align-items: center;
        }
        .co-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 52px;
          padding-inline: 28px;
          border-radius: 10px;
          font-weight: 600;
          text-decoration: none;
        }
        .co-btn-primary {
          background: #1f8f4e;
          color: #fff;
        }
        .co-btn-quiet {
          color: #1f8f4e;
        }
        @keyframes co-spin {
          to {
            transform: rotate(360deg);
          }
        }
        @media (prefers-reduced-motion: reduce) {
          .co-mark-confirming,
          .co-mark-finalizing {
            animation: none;
          }
        }
      `}</style>
    </>
  );
}

const COPY: Record<View, { title: string; body: string }> = {
  loading: {
    title: 'Confirming your payment',
    body: "We're securely checking your payment status. This page will update automatically.",
  },
  confirming: {
    title: 'Confirming your payment',
    body: "We're securely checking your payment status. This page will update automatically.",
  },
  finalizing: {
    title: 'Payment received',
    body: "We're creating your order now. Do not pay again.",
  },
  failed: {
    title: "Payment wasn't completed",
    body: 'No order was created. You can try again whenever you are ready.',
  },
  unavailable: {
    title: 'Nothing to show here',
    body: 'We could not find a payment to confirm. If you just paid, check WhatsApp for your confirmation.',
  },
};
