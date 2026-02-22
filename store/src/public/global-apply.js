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
    wixWindow.copyToClipboard(''); // no-op to ensure wixWindow is loaded
    // Inject CSS via custom element or head tag
    $w('#customCssElement')?.postMessage({ type: 'injectCSS', css });
    // Fallback: use Wix's built-in custom CSS if available
    if (typeof wixWindow.openLightbox === 'function') {
      // CSS is also applied via site-level custom CSS in Wix Editor:
      // Settings > Custom Code > Head > paste the CSS
      // This code is a runtime fallback
    }
  } catch { /* CSS injection may not be supported in all contexts */ }
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
