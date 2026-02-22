/**
 * Hide Wix Native Order Number — WECARE.DIGITAL
 *
 * Strategies to permanently suppress the Wix native sequential order number
 * (e.g. #10001) and only show the WDSR custom order ID everywhere.
 *
 * Wix shows the native order number in:
 *   1. Thank You page (post-checkout)
 *   2. My Orders page (Members Area)
 *   3. Order confirmation emails
 *   4. Wix Dashboard (admin side — can't fully hide)
 *   5. Wix Owner App (mobile)
 *
 * What we CAN control via Velo:
 *   ✓ Thank You page — replace via page code (Thank You.js)
 *   ✓ My Orders page — custom page replaces Members Area default (My Orders.js)
 *   ✓ Order confirmation emails — use Triggered Emails with custom fields
 *   ✓ Site pages — CSS injection hides native number elements
 *   ✗ Wix Dashboard — native number always visible to admin (acceptable)
 *   ✗ Wix Owner App — limited control, but customField shows WDSR
 *
 * This module provides:
 *   1. CSS injection to hide native order number elements on all pages
 *   2. DOM replacement to swap native number with WDSR where CSS can't reach
 *   3. Email template helper to format WDSR for Triggered Emails
 *
 * IMPORTANT: The Wix eCommerce "customField" on orders is the key mechanism.
 * When we set customField.title = "Order ID" and customField.value = "WDSR-...",
 * Wix shows this in the Owner App and some native UI elements.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-ecom/orders
 */

/**
 * CSS to inject on every page to hide Wix native order number elements.
 * Targets known Wix Stores CSS classes for order number display.
 *
 * Call this from global-apply.js:
 *   import { injectHideNativeOrderCSS } from 'backend/hide-native-order-number.js';
 *   injectHideNativeOrderCSS();
 */
export function getHideNativeOrderCSS() {
  return `
    /* Hide Wix native order number across all store pages */
    /* Thank You page native order number */
    [data-hook="thank-you-page-order-number"],
    [data-hook="order-number"],
    .thank-you-page__order-number,
    .orderNumber,
    /* Members Area — My Orders native number */
    [data-hook="order-row-number"],
    [data-hook="order-details-number"],
    .order-number-value,
    /* Order confirmation page */
    [data-hook="confirmation-order-number"] {
      display: none !important;
      visibility: hidden !important;
      height: 0 !important;
      overflow: hidden !important;
    }

    /* Make the custom field (WDSR) more prominent where Wix shows it */
    [data-hook="order-custom-field"],
    [data-hook="custom-field-value"] {
      font-weight: 700 !important;
      font-size: 1.1em !important;
    }
  `;
}

/**
 * Format order data for Triggered Email variables.
 * Use this when sending order confirmation emails via Wix Triggered Emails.
 *
 * In Wix Dashboard > Triggered Emails, create a template with variable:
 *   {{orderNumber}} — will receive the WDSR number, NOT the native number
 *
 * @param {object} order - The order object
 * @param {string} customOrderNumber - The WDSR number
 * @returns {object} Variables for triggeredEmails.emailMember()
 */
export function buildEmailVariables(order, customOrderNumber) {
  const buyer = order.buyerInfo || {};
  const totals = order.priceSummary || order.totals || {};
  const billing = order.billingInfo?.contactDetails || {};

  return {
    orderNumber: customOrderNumber, // WDSR — NOT the native number
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
  };
}
