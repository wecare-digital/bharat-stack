/**
 * Global Site Code — WECARE.DIGITAL
 *
 * Runs on every page load. Handles:
 *   - Consent banner / cookie notice
 *   - Global analytics event tracking
 *   - WhatsApp chat widget initialization
 *   - Cart badge update
 *
 * Place in: Public & Backend > Public > global-apply.js
 * Wix Editor: Site tab > Global (masterPage.js equivalent)
 */

import wixWindow from 'wix-window';
import wixLocation from 'wix-location';
import { getHideNativeOrderCSS } from 'backend/hide-native-order-number.js';

$w.onReady(function () {
  // Skip in preview/editor mode
  if (wixWindow.rendering.env === 'backend') return;

  injectCustomCSS();
  initAnalytics();
  initWhatsAppWidget();
  updateCartBadge();
});

// ---------------------------------------------------------------------------
// Hide Wix Native Order Number (CSS injection)
// ---------------------------------------------------------------------------

function injectCustomCSS() {
  try {
    const css = getHideNativeOrderCSS();
    // Inject CSS via custom element
    try { $w('#customCssElement')?.postMessage({ type: 'injectCSS', css }); } catch {}

    // Also inject via Wix's CustomElement API if available
    try {
      const styleEl = $w('#hiddenStyleInjector');
      if (styleEl) styleEl.postMessage({ type: 'style', css });
    } catch {}
  } catch { /* CSS injection may not be supported in all contexts */ }

  // DOM-based: hide any element containing only a native order number pattern (#XXXXX)
  // and replace with WD custom order ID if available
  try {
    hideNativeOrderNumbersOnPage();
  } catch {}
}

/**
 * Scan page for native Wix order number patterns and hide them.
 * Looks for text matching #XXXXX (5+ digit native order number).
 */
function hideNativeOrderNumbersOnPage() {
  // Wix native order numbers are typically 5+ digit numbers prefixed with #
  // We hide any text element that shows only a native order number
  const selectors = [
    '#orderNumber', '#nativeOrderNumber', '#orderRef',
    '#orderConfirmationNumber', '#thankYouOrderId',
  ];
  for (const sel of selectors) {
    try {
      const el = $w(sel);
      if (el && el.text) {
        // If it looks like a native Wix order number (just digits or #digits), hide it
        const text = el.text.trim();
        if (/^#?\d{4,}$/.test(text)) {
          el.hide();
        }
      }
    } catch {}
  }
}

// ---------------------------------------------------------------------------
// Analytics
// ---------------------------------------------------------------------------

function initAnalytics() {
  const page = wixLocation.path.join('/') || 'home';

  // Track page view
  wixWindow.trackEvent('PageView', {
    page,
    url: wixLocation.url,
    referrer: wixWindow.referrer || '',
    timestamp: new Date().toISOString(),
  });

  // Track outbound link clicks
  $w('a').forEach((link) => {
    try {
      link.onClick(() => {
        const href = link.link || '';
        if (href.startsWith('http') && !href.includes('wecare.digital')) {
          wixWindow.trackEvent('OutboundClick', { url: href, page });
        }
      });
    } catch { /* some elements may not support onClick */ }
  });
}

// ---------------------------------------------------------------------------
// WhatsApp Chat Widget
// ---------------------------------------------------------------------------

function initWhatsAppWidget() {
  // WhatsApp floating button — uses Wix Chat or custom element
  // The phone number and pre-filled message are configured in the Wix Editor
  // This just ensures the widget is visible on all pages
  try {
    const chatWidget = $w('#whatsappChat');
    if (chatWidget) {
      chatWidget.show();
    }
  } catch { /* widget may not exist on all pages */ }
}

// ---------------------------------------------------------------------------
// Cart Badge
// ---------------------------------------------------------------------------

async function updateCartBadge() {
  try {
    const { cart } = await import('wix-stores-frontend');
    const currentCart = await cart.getCurrentCart();
    const itemCount = (currentCart?.lineItems || []).reduce(
      (sum, item) => sum + (item.quantity || 0), 0
    );

    const badge = $w('#cartBadge');
    if (badge) {
      if (itemCount > 0) {
        badge.text = String(itemCount);
        badge.show();
      } else {
        badge.hide();
      }
    }
  } catch { /* cart API may not be available */ }
}
