/**
 * Checkout success — the order-created confirmation screen (Wix-Velo prompt §48).
 *
 * It is reached only after the status screen has seen a PAID attempt WITH an order number, so by
 * the time a customer lands here an order genuinely exists. It shows the essentials and points at
 * WhatsApp for the real thing:
 *
 *   - a success indicator and the 12/15-character public order number (WD-ORD-…)
 *   - Track order / Continue shopping
 *   - a clear statement that the full receipt and confirmation are in WhatsApp
 *
 * The website deliberately reflects status and essential order info only. The authoritative
 * receipt is delivered over WhatsApp, once, by the reconciliation path — this page never renders a
 * receipt or an amount as if it were the record of the sale.
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
 */

import Head from 'next/head';
import React, { useEffect, useState } from 'react';

function orderNumberFromUrl (): string {
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
      <main className="cs-wrap">
        <section className="cs-card">
          <div className="cs-mark" aria-hidden="true">✓</div>
          <h1 className="cs-title">Payment successful</h1>
          <p className="cs-body">
            Your order has been created. We&apos;ve sent your confirmation and receipt to WhatsApp.
          </p>

          {orderNumber && (
            <p className="cs-order">
              <span className="cs-order-label">Order number</span>
              <span className="cs-order-number">{orderNumber}</span>
            </p>
          )}

          <div className="cs-actions">
            <a className="cs-btn cs-btn-primary" href="/shop/">Continue shopping</a>
            <a className="cs-btn cs-btn-quiet" href="/">Back to home</a>
          </div>
        </section>
      </main>

      <style jsx>{`
        .cs-wrap {
          min-height: 100vh;
          min-height: 100dvh;
          display: flex;
          align-items: center;
          justify-content: center;
          padding-block: 48px;
          padding-inline: 20px;
        }
        .cs-card {
          width: 100%;
          max-inline-size: 30rem;
          text-align: center;
        }
        .cs-mark {
          inline-size: 64px;
          block-size: 64px;
          margin-inline: auto;
          margin-block-end: 24px;
          border-radius: 50%;
          background: #1f8f4e;
          color: #fff;
          font-size: 34px;
          line-height: 64px;
        }
        .cs-title {
          font-size: clamp(26px, 3.4vw, 34px);
          font-weight: 700;
          line-height: 1.1;
          letter-spacing: -0.02em;
          margin: 0 0 12px;
        }
        .cs-body {
          font-size: 16px;
          line-height: 1.5;
          color: #444;
          margin: 0;
        }
        .cs-order {
          margin-block-start: 28px;
          display: flex;
          flex-direction: column;
          gap: 4px;
        }
        .cs-order-label {
          font-size: 13px;
          text-transform: uppercase;
          letter-spacing: 0.08em;
          color: #777;
        }
        .cs-order-number {
          font-size: 22px;
          font-weight: 700;
          letter-spacing: 0.04em;
          font-variant-numeric: tabular-nums;
        }
        .cs-actions {
          margin-block-start: 32px;
          display: flex;
          flex-direction: column;
          gap: 12px;
          align-items: center;
        }
        .cs-btn {
          display: inline-flex;
          align-items: center;
          justify-content: center;
          min-height: 52px;
          padding-inline: 28px;
          border-radius: 10px;
          font-weight: 600;
          text-decoration: none;
        }
        .cs-btn-primary {
          background: #1f8f4e;
          color: #fff;
        }
        .cs-btn-quiet {
          color: #1f8f4e;
        }
      `}</style>
    </>
  );
}
