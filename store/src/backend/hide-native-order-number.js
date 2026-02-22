/**
 * Hide Wix Native Order Number — WECARE.DIGITAL
 *
 * Permanently suppress the Wix native sequential order number (#10001)
 * and only show the WD custom order ID (WD-ORD-YYYYMMDD-XXXX) everywhere.
 *
 * Wix shows the native order number in:
 *   1. Thank You page (post-checkout)
 *   2. My Orders page (Members Area)
 *   3. Order confirmation emails
 *   4. Wix Dashboard (admin side — can't fully hide)
 *   5. Wix Owner App (mobile)
 *   6. Order details inner page
 *   7. Wix-branded notification emails
 *
 * What we CAN control via Velo:
 *   ✓ Thank You page — replace via page code (Thank You.js)
 *   ✓ My Orders page — custom page replaces Members Area default (My Orders.js)
 *   ✓ Order confirmation emails — use Triggered Emails with custom fields
 *   ✓ Site pages — CSS injection hides native number elements
 *   ✓ Order details inner page — CSS + DOM replacement
 *   ✓ customField on order — shows WD in Owner App and native emails
 *   ✗ Wix Dashboard — native number always visible to admin (acceptable)
 *
 * This module provides:
 *   1. CSS injection to hide native order number elements on ALL pages
 *   2. DOM replacement to swap native number with WD where CSS can't reach
 *   3. Email template helper to format WD for Triggered Emails
 *   4. Wix branding suppression CSS
 */

/**
 * CSS to inject on every page to hide Wix native order number elements
 * and suppress Wix branding where possible.
 *
 * Call from global-apply.js:
 *   import { getHideNativeOrderCSS } from 'backend/hide-native-order-number.js';
 */
export function getHideNativeOrderCSS() {
  return `
    /* ============================================================
       HIDE WIX NATIVE ORDER NUMBER — ALL PAGES
       ============================================================ */

    /* Thank You page */
    [data-hook="thank-you-page-order-number"],
    [data-hook="order-number"],
    [data-hook="thankyou-page-order-number"],
    .thank-you-page__order-number,
    .orderNumber,
    .ThankYouPage__orderNumber,

    /* Members Area — My Orders list */
    [data-hook="order-row-number"],
    [data-hook="order-details-number"],
    [data-hook="order-list-item-number"],
    [data-hook="my-orders-order-number"],
    .order-number-value,
    .OrderHistory__orderNumber,

    /* Order details inner page */
    [data-hook="order-details-order-number"],
    [data-hook="order-info-number"],
    [data-hook="order-summary-number"],
    [data-hook="order-number-label"],
    .OrderDetails__orderNumber,
    .order-details__number,

    /* Order confirmation page */
    [data-hook="confirmation-order-number"],
    [data-hook="order-confirmation-number"],

    /* Cart / Checkout native order ref */
    [data-hook="checkout-order-number"],

    /* Wix native "Order #XXXXX" text pattern */
    .wix-order-number,
    .native-order-number {
      display: none !important;
      visibility: hidden !important;
      height: 0 !important;
      overflow: hidden !important;
      opacity: 0 !important;
      position: absolute !important;
      pointer-events: none !important;
    }

    /* ============================================================
       MAKE WD CUSTOM ORDER ID PROMINENT
       ============================================================ */

    [data-hook="order-custom-field"],
    [data-hook="custom-field-value"],
    [data-hook="order-custom-field-value"],
    .custom-order-id,
    .wd-order-number {
      font-weight: 700 !important;
      font-size: 1.15em !important;
      color: #1a1a2e !important;
    }

    /* ============================================================
       SUPPRESS WIX BRANDING (where allowed by plan)
       ============================================================ */

    /* "Powered by Wix" footer */
    [data-hook="powered-by-wix"],
    .powered-by-wix,
    #WIX_ADS,
    .wix-ads,

    /* Wix logo in emails (if rendered on site) */
    [data-hook="wix-logo"],
    .wix-branding,

    /* Wix app badges */
    [data-hook="wix-badge"],
    .wix-badge-container {
      display: none !important;
      visibility: hidden !important;
    }
  `;
}

/**
 * Format order data for Triggered Email variables.
 * Use this when sending order confirmation emails via Wix Triggered Emails.
 *
 * In Wix Dashboard > Triggered Emails, create a template with variable:
 *   {{orderNumber}} — will receive the WD number, NOT the native number
 *
 * @param {object} order - The order object
 * @param {string} customOrderNumber - The WD number (e.g. WD-ORD - A3F7B2C1 - 22-02-2026 - 17:43:01 - IST)
 * @returns {object} Variables for triggeredEmails.emailMember()
 */
export function buildEmailVariables(order, customOrderNumber) {
  const buyer = order.buyerInfo || {};
  const totals = order.priceSummary || order.totals || {};
  const billing = order.billingInfo?.contactDetails || {};

  return {
    orderNumber: customOrderNumber, // WD — NOT the native number
    buyerName: `${billing.firstName || ''} ${billing.lastName || ''}`.trim() || buyer.email || 'Customer',
    buyerEmail: buyer.email || '',
    totalAmount: totals.total?.amount || totals.total || '0',
    currency: order.currency || 'INR',
    itemCount: String(order.lineItems?.length || 0),
    orderDate: new Date(order._dateCreated || order.createdDate || Date.now()).toLocaleDateString('en-IN', {
      day: 'numeric',
      month: 'short',
      year: 'numeric',
    }),
    paymentStatus: (order.paymentStatus || '').replace(/_/g, ' '),
    fulfillmentStatus: (order.fulfillmentStatus || 'NOT FULFILLED').replace(/_/g, ' '),
    siteUrl: 'https://www.wecare.digital',
    supportWhatsApp: '+91 93309 94400',
    supportEmail: 'visa@wecare.digital',
  };
}
