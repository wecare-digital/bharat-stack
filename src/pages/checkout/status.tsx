/**
 * Checkout status — the payment handoff/status screen.
 *
 * What this screen is, and is not
 * -------------------------------
 * It is a STATUS MIRROR, not a second checkout. It cannot choose an amount, an account, a return
 * URL or a payment outcome — every one of those is decided server-side and this page only reflects
 * what the backend already knows. It never asks anyone to pay here.
 *
 * The five states it renders come straight from the payment-attempt state machine:
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
 * A paid-but-finalizing state must NEVER offer a retry, and whether an attempt is terminally failed
 * is the state machine's call to make rather than the browser's — "still pending" and "definitely
 * failed" look identical from here. So the only view carrying an action that starts a new checkout
 * is `failed`, which is reached solely from an explicit PAYMENT_FAILED / PAYMENT_CANCELLED /
 * PAYMENT_EXPIRED. The paid, pending and unknown views carry no retry at all.
 *
 * NOTHING ON THIS PAGE SAYS "no charge was made", and that absence is the point. The two states a
 * visitor is most likely to land on are "in flight" and "unknown", and in both of them the money
 * may in fact have been captured — the browser cannot tell. Claiming no charge to reassure someone
 * is the one wrong answer that cannot be taken back, so the copy says what is known (we are
 * checking; we could not find it) and never what is not.
 *
 * Degrades without JavaScript
 * ---------------------------
 * The settled markup is the "Confirming…" state written into the DOM, so a no-JS load shows a
 * coherent screen. The polling only ever refines it.
 *
 * Chrome and clearance
 * --------------------
 * THE TOP BAND IS SHARED NOW, AND IT HAD TO BE. This page used to centre a card inside
 * min-height:100vh with NO header clearance at all and no font stack declared, so its heading
 * painted underneath the 108px fixed header and its typeface depended on an Amplify stylesheet
 * happening to set one on body. components/PageTopBand owns the main landmark, the h1, both header
 * heights, the measure and the entrance animation, which is the whole of skill §6 that this screen
 * was missing.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useCallback, useEffect, useState } from 'react';

import PageTopBand from '../../components/PageTopBand';
import { getSession } from '../../lib/customerAuth';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || 'https://wecare.digital/api';
const CHECKOUT_STATUS_URL = `${API_BASE}/ecommerce/checkout/status`;

/** How often the screen re-asks the backend while a payment is in flight. */
const POLL_INTERVAL_MS = 4000;
/** Stop polling after this long; the customer can refresh. Bounds a stuck tab. */
const POLL_CEILING_MS = 5 * 60 * 1000;

type View =
  | 'confirming'
  | 'finalizing'
  | 'failed'
  | 'unavailable';

interface AttemptView {
  status?: string;
  orderNumber?: string | null;
  canRetry?: boolean;
}

/** Which of the four screens a backend status maps to. Redirect to success is handled separately. */
export function viewFor ( status: string | undefined, orderNumber: string | null | undefined ): View {
  const s = String( status || '' ).toUpperCase();
  if ( s === 'PAYMENT_PAID' )
  {
    // With an order number the redirect fires and this value is momentary; without one the order
    // is still being created, which is its own screen and never offers a retry.
    return orderNumber ? 'confirming' : 'finalizing';
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
  // never claims success, never claims nothing was charged, and never invites a second payment.
  return 'unavailable';
}

function attemptIdFromUrl (): string {
  if ( typeof window === 'undefined' ) return '';
  const params = new URLSearchParams( window.location.search );
  return String( params.get( 'a' ) || '' ).trim();
}

/**
 * The copy for each state.
 *
 * SHORTENED ON OWNER INSTRUCTION, WITH NO GUARANTEE DROPPED. "We're securely checking your payment
 * status. This page will update automatically." became two short sentences that say the same two
 * things. "Do not pay again" stays verbatim on the finalizing screen: it is the one sentence on this
 * page that prevents a double charge.
 */
const COPY: Record<View, { title: string; body: string }> = {
  confirming: {
    title: 'Confirming your payment',
    body: 'We are checking with the payment provider. This page updates on its own.',
  },
  finalizing: {
    title: 'Payment received',
    body: 'We are creating your order now. Do not pay again.',
  },
  failed: {
    title: "Payment wasn't completed",
    body: 'No order was created. You can start again whenever you are ready.',
  },
  unavailable: {
    title: 'Nothing to show here',
    body: 'We could not find a payment to confirm. If you have just paid, check WhatsApp for your confirmation.',
  },
};

export default function CheckoutStatus (): React.ReactElement {
  // The settled server state is "confirming": a no-JS load shows a coherent, honest screen rather
  // than a blank one. Polling only ever refines this.
  const [ view, setView ] = useState<View>( 'confirming' );

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
      return undefined;
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
      {/* The h1 is the STATE, which is what this page is about, so the band's heading changes with
          it. There is no CTA in the band: the actions sit below, per skill §6. */}
      <PageTopBand heading={ copy.title } sub={ copy.body } ariaLabel="Checkout status">
        <section className="co-card" role="status" aria-live="polite">
          <div className={ `co-mark co-mark-${view}` } aria-hidden="true" />

          {view === 'finalizing' && (
            <p className="co-note">Keep this page open. It usually takes a few seconds.</p>
          )}

          {view === 'failed' && (
            <div className="co-actions">
              {/* Starting again means a NEW checkout - new reference, re-priced by the store. This
                  page never re-sends a payment itself, and this action exists only because the
                  backend has confirmed the attempt is terminally failed. */}
              <Link className="co-btn co-btn-primary" href="/shop/">Start again</Link>
              <Link className="co-btn co-btn-quiet" href="/">Back to home</Link>
            </div>
          )}

          {view === 'unavailable' && (
            <div className="co-actions">
              {/* NOT a primary action, and not a retry. This state covers "initiation is off" and
                  "we cannot find this attempt", and in neither can the browser rule out that money
                  moved - so the only thing offered is a way back to the store. */}
              <Link className="co-btn co-btn-quiet" href="/shop/">Return to the store</Link>
            </div>
          )}
        </section>

        <style jsx>{`
          /* No top padding, no measure, no font stack: PageTopBand owns all three. 700px is the
             measure the rest of the site gives a column of body copy. */
          .co-card{width:100%;max-width:700px;margin:0}

          /* 56px spinner, and the ONLY colour in it is the palette's own grassy green #3da35a.
             It was #1f8f4e, which appears nowhere in the home design. The track is the site's
             rgba(0,0,0,.12) hairline. */
          .co-mark{
            inline-size:56px;block-size:56px;margin-block-end:24px;border-radius:50%;
          }
          .co-mark-confirming,
          .co-mark-finalizing{
            border:3px solid rgba(0,0,0,.12);
            border-block-start-color:#3da35a;
            animation:co-spin 900ms linear infinite;
          }
          /* NO RED on the failed mark, on owner instruction. It was #fbe9e9, a pink wash that
             exists nowhere else on this site. Both terminal marks are now neutral discs at the
             site's own alpha: the heading above states the outcome, so the disc is a position
             marker and not the message. */
          .co-mark-failed,
          .co-mark-unavailable{background:rgba(0,0,0,.06)}

          .co-note{
            margin:0;font-size:16px;line-height:1.55;color:rgba(0,0,0,.54);
          }
          .co-actions{
            margin-block-start:28px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;
          }
          /* THE SITE CTA, NOT A 10px GREEN RECTANGLE. These were #1f8f4e fills with white text on
             a 10px radius - a colour and a shape the home design does not use. The primary is now
             the one lime surface this page is allowed: 52px, #d1f470 with #1a3a2a type, a 2px
             border because 2px means hoverable, the 50px pill radius, and the 2px lift with the
             single shadow this language allows.
             :global() IS MANDATORY: these are next/link, and styled-jsx attaches its scoping class
             only to lowercase DOM tags it can see in this file - a capitalised component never gets
             it, because styled-jsx cannot know whether the component forwards className to a DOM
             node. Without it the compiled rule matches nothing and both render as bare blue
             underlined text. */
          .co-card :global(.co-btn){
            display:inline-flex;align-items:center;justify-content:center;min-height:52px;
            padding-inline:26px;border-radius:50px;font-family:inherit;font-size:17px;
            font-weight:600;text-decoration:none;line-height:normal;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .co-card :global(.co-btn-primary){
            background:#d1f470;border:2px solid #d1f470;color:#1a3a2a;
          }
          .co-card :global(.co-btn-primary:hover){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          /* The quiet action is a 2px lime outline rather than a second lime fill, so the page
             still has exactly one lime surface. */
          .co-card :global(.co-btn-quiet){
            background:#fff;border:2px solid #d1f470;color:#1a3a2a;
          }
          .co-card :global(.co-btn-quiet:hover){background:rgba(209,244,112,.22)}
          .co-card :global(.co-btn:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px}

          @keyframes co-spin{to{transform:rotate(360deg)}}

          @media(prefers-reduced-motion:reduce){
            .co-mark-confirming,
            .co-mark-finalizing{animation:none}
            .co-card :global(.co-btn){transition:none}
            .co-card :global(.co-btn:hover){transform:none;box-shadow:none}
          }
        `}</style>
      </PageTopBand>
    </>
  );
}
