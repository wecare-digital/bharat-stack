/**
 * Thank You / Order Confirmation Page — WECARE.DIGITAL
 *
 * Velo page code for the post-checkout thank you page.
 * Displays ONLY the WD custom order number.
 * Wix native order number is hidden via CSS + DOM replacement.
 *
 * Wix Editor: Pages > Thank You Page
 */

import wixWindow from 'wix-window';
import wixLocation from 'wix-location';
import { createOrGetOrderId } from 'backend/orderId.web.js';
import { getHideNativeOrderCSS } from 'backend/hide-native-order-number.js';
import { cleanConsole } from 'public/site-hygiene.js';

$w.onReady(async function () {
  cleanConsole();

  // Hide Wix native order number elements
  hideNativeOrderNumber();

  // The order ID is passed via query parameter or the thank you page context
  const orderId = wixLocation.query?.orderId;
  if (!orderId) return;

  // Fetch and display WD custom order number
  try {
    const wdNumber = await createOrGetOrderId({ wixOrderId: orderId });

    // Show WD in our custom element
    const orderNumEl = $w('#customOrderNumber');
    if (orderNumEl && wdNumber) {
      orderNumEl.text = wdNumber;
      orderNumEl.show();
    }

    // Also try to replace any native order number text on the page
    // with the WD number (for Wix's built-in thank you components)
    replaceNativeWithWD(wdNumber);

  } catch { /* custom order number may not be available yet */ }

  // Track purchase event
  trackPurchase(orderId);
});

// ---------------------------------------------------------------------------
// Hide / Replace Native Order Number
// ---------------------------------------------------------------------------

function hideNativeOrderNumber() {
  try {
    // Hide known Wix native order number elements
    const nativeElements = [
      '#orderNumber',        // Common Wix thank you page element
      '#nativeOrderNumber',
    ];
    for (const sel of nativeElements) {
      try { $w(sel)?.hide(); } catch { /* element may not exist */ }
    }
  } catch { /* ignore */ }
}

function replaceNativeWithWD(wdNumber) {
  if (!wdNumber) return;
  try {
    // Try to find and replace text in Wix's built-in order confirmation elements
    const possibleElements = ['#orderConfirmationNumber', '#orderRef', '#thankYouOrderId'];
    for (const sel of possibleElements) {
      try {
        const el = $w(sel);
        if (el && el.text) {
          el.text = wdNumber;
        }
      } catch { /* element may not exist */ }
    }
  } catch { /* ignore */ }
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

function trackPurchase(orderId) {
  try {
    wixWindow.trackEvent('Purchase', {
      origin: 'Stores',
      orderId,
      source: 'wecare-digital',
      timestamp: new Date().toISOString(),
    });
  } catch { /* tracking may fail silently */ }
}
