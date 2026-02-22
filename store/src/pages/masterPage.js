/**
 * Master Page (Global Site Code) — WECARE.DIGITAL
 *
 * Runs on every page load across the entire site.
 * This is the Wix equivalent of masterPage.js / Site tab code.
 *
 * Handles:
 *   - CSS injection to hide Wix native order numbers
 *   - Global analytics event tracking
 *   - WhatsApp chat widget initialization
 *   - Cart badge update
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
    try { $w('#customCssElement')?.postMessage({ type: 'injectCSS', css }); } catch {}
    try {
      const styleEl = $w('#hiddenStyleInjector');
      if (styleEl) styleEl.postMessage({ type: 'style', css });
    } catch {}
  } catch {}

  try {
    hideNativeOrderNumbersOnPage();
  } catch {}
}

function hideNativeOrderNumbersOnPage() {
  const selectors = [
    '#orderNumber', '#nativeOrderNumber', '#orderRef',
    '#orderConfirmationNumber', '#thankYouOrderId',
  ];
  for (const sel of selectors) {
    try {
      const el = $w(sel);
      if (el && el.text) {
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

  wixWindow.trackEvent('PageView', {
    page,
    url: wixLocation.url,
    referrer: wixWindow.referrer || '',
    timestamp: new Date().toISOString(),
  });

  $w('a').forEach((link) => {
    try {
      link.onClick(() => {
        const href = link.link || '';
        if (href.startsWith('http') && !href.includes('wecare.digital')) {
          wixWindow.trackEvent('OutboundClick', { url: href, page });
        }
      });
    } catch {}
  });
}

// ---------------------------------------------------------------------------
// WhatsApp Chat Widget
// ---------------------------------------------------------------------------

function initWhatsAppWidget() {
  try {
    const chatWidget = $w('#whatsappChat');
    if (chatWidget) chatWidget.show();
  } catch {}
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
  } catch {}
}
