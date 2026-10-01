/**
 * Checkout success — the order-created confirmation screen.
 *
 * It is reached only after the status screen has seen a PAID attempt WITH an order number, so by
 * the time a customer lands here an order genuinely exists. It shows the essentials and points at
 * WhatsApp for the real thing:
 *
 *   - the 12/15-character public order number (WD-ORD-…)
 *   - Continue shopping / Back to home
 *   - a clear statement that the full receipt and confirmation are in WhatsApp
 *
 * The website deliberately reflects status and essential order info only. The authoritative receipt
 * is delivered over WhatsApp, once, by the reconciliation path — this page never renders a receipt
 * or an amount as if it were the record of the sale. There is no download here because there is no
 * endpoint to download from; a button that 404s would be worse than none. See
 * docs/execution/website-payment-handover.md for what has to exist first.
 *
 * The order number in the URL is not an authority
 * -----------------------------------------------
 * `?o=<orderNumber>` is a display value the status page already resolved for THIS customer's own
 * paid attempt. It is safe to show back because knowing an order number authorises nothing —
 * tracking and receipts are gated by the customer session, never by the number (see
 * customer_auth: "Never authorise on an identifier from the request"). A stranger pasting a guessed
 * number sees only what this static page renders from the string itself: a heading. Nothing is
 * fetched here without a session.
 *
 * No-JS
 * -----
 * The success copy is static markup. If scripting is off the only thing that does not appear is the
 * order number read from the query string, so the page still reads as a coherent confirmation.
 *
 * Chrome and clearance
 * --------------------
 * THE TOP BAND IS SHARED NOW, AND IT HAD TO BE. This page used to centre a card inside
 * min-height:100vh with NO header clearance and no font stack declared, so its heading painted
 * under the 108px fixed header and its typeface was a side effect of an Amplify stylesheet.
 * components/PageTopBand owns the main landmark, the h1, both header heights, the measure and the
 * entrance animation.
 */

import Head from 'next/head';
import Link from 'next/link';
import React, { useEffect, useState } from 'react';

import PageTopBand from '../../components/PageTopBand';

export function orderNumberFromUrl (): string {
  if ( typeof window === 'undefined' ) return '';
  const params = new URLSearchParams( window.location.search );
  const raw = String( params.get( 'o' ) || '' ).trim();
  // Display-only sanitisation: the public number is uppercase A-Z/0-9 with dashes. Anything else
  // is not one of ours, so show nothing rather than reflect arbitrary text back into the page.
  return /^[A-Z0-9-]{8,20}$/.test( raw ) ? raw : '';
}

export default function CheckoutSuccess (): React.ReactElement {
  const [ orderNumber, setOrderNumber ] = useState<string>( '' );

  useEffect( () => {
    setOrderNumber( orderNumberFromUrl() );
  }, [] );

  return (
    <>
      <Head>
        <title>Payment successful — WECARE.DIGITAL</title>
        <meta name="robots" content="noindex,nofollow" />
      </Head>
      <PageTopBand
        heading="Payment successful"
        sub="Your order is created. The confirmation and receipt are on WhatsApp."
        ariaLabel="Payment successful"
      >
        <section className="cs-card">
          {/* THE TICK IS DRAWN FROM BORDERS, NOT TYPED. The old mark was the literal character ✓
              inside a filled disc, so its shape and weight varied by platform font - the same
              reason the header's chevron is two borders. A tick is an ORIENTATION rather than a
              side, so it is NOT mirrored under rtl: a flipped tick reads as a cross. */}
          <div className="cs-mark" aria-hidden="true"><i className="cs-tick" /></div>

          {orderNumber && (
            <p className="cs-order">
              <span className="cs-order-label">Order number</span>
              {/* data-wc-no-translate: this is an identifier, and a translated or regrouped
                  WD-ORD-… is a different string. The same reason the prices carry it. */}
              <span className="cs-order-number" data-wc-no-translate="true">{orderNumber}</span>
            </p>
          )}

          <div className="cs-actions">
            <Link className="cs-btn cs-btn-primary" href="/shop/">Continue shopping</Link>
            <Link className="cs-btn cs-btn-quiet" href="/">Back to home</Link>
          </div>
        </section>

        <style jsx>{`
          /* No top padding, no measure, no font stack: PageTopBand owns all three. */
          .cs-card{width:100%;max-width:700px;margin:0}

          /* The disc is the palette's grassy green #3da35a, not #1f8f4e - that value appears
             nowhere in the home design. 56px matches the status screen's mark, so the two
             checkout screens agree on the size of their one piece of iconography. */
          .cs-mark{
            inline-size:56px;block-size:56px;border-radius:50%;background:#3da35a;
            display:flex;align-items:center;justify-content:center;margin-block-end:24px;
          }
          /* Two borders on a rotated box: 10px x 20px, bottom and inline-end stroked at 3px,
             rotated 45deg. Deliberately NOT mirrored for rtl - see the note on the markup. */
          .cs-tick{
            inline-size:10px;block-size:20px;box-sizing:border-box;
            border-right:3px solid #fff;border-bottom:3px solid #fff;
            transform:rotate(45deg) translateY(-2px);
          }

          .cs-order{margin:0;display:flex;flex-direction:column;gap:6px}
          /* The dim rung at rgba(0,0,0,.54), not #777. Tracking in em on a fixed size is fine -
             the em rule is about clamp() sizes, where a px value makes optical tightness swing
             with the viewport. */
          .cs-order-label{
            font-size:14px;font-weight:700;text-transform:uppercase;letter-spacing:.08em;
            color:rgba(0,0,0,.54);
          }
          /* The card-heading rung in dark green - the same 22px/700/1.27/-.25px the catalogue
             gives a price, because this is the other identifier a customer reads back to us.
             Tabular figures so the digits are evenly spaced. */
          .cs-order-number{
            font-size:22px;font-weight:700;line-height:1.27;letter-spacing:-.25px;
            color:#1a3a2a;font-variant-numeric:tabular-nums;
          }

          .cs-actions{
            margin-block-start:32px;display:flex;flex-wrap:wrap;gap:12px;align-items:center;
          }
          /* THE SITE CTA, NOT A 10px GREEN RECTANGLE. These were #1f8f4e fills with white text on
             a 10px radius. The primary is the one lime surface this page is allowed: 52px, #d1f470
             with #1a3a2a type, 2px border (2px means hoverable), 50px pill radius, 2px lift.
             :global() IS MANDATORY - these are next/link, and styled-jsx does not scope a
             capitalised component, so without it the compiled rule matches nothing and both render
             as bare blue underlined text. */
          .cs-card :global(.cs-btn){
            display:inline-flex;align-items:center;justify-content:center;min-height:52px;
            padding-inline:26px;border-radius:50px;font-family:inherit;font-size:17px;
            font-weight:600;text-decoration:none;line-height:normal;
            transition:background-color .2s,transform .2s,box-shadow .2s;
          }
          .cs-card :global(.cs-btn-primary){
            background:#d1f470;border:2px solid #d1f470;color:#1a3a2a;
          }
          .cs-card :global(.cs-btn-primary:hover){background:#fff;transform:translateY(-2px);box-shadow:0 4px 12px rgba(26,58,42,.12)}
          /* Outlined rather than a second lime fill, so the page keeps exactly one lime surface. */
          .cs-card :global(.cs-btn-quiet){
            background:#fff;border:2px solid #d1f470;color:#1a3a2a;
          }
          .cs-card :global(.cs-btn-quiet:hover){background:rgba(209,244,112,.22)}
          .cs-card :global(.cs-btn:focus-visible){outline:3px solid #1a3a2a;outline-offset:3px}

          @media(prefers-reduced-motion:reduce){
            .cs-card :global(.cs-btn){transition:none}
            .cs-card :global(.cs-btn:hover){transform:none;box-shadow:none}
          }
        `}</style>
      </PageTopBand>
    </>
  );
}
