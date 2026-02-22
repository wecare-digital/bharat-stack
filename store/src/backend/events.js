/**
 * Wix Events — WECARE.DIGITAL
 *
 * Auto-triggered backend event handlers.
 *
 * Events:
 *   - wixStores_onProductCreated: Auto-assign SKU to new products
 *   - wixEcom_onOrderCreated: Generate custom order ID (WDSR prefix)
 *
 * The order ID generation delegates to orderId.web.js to avoid
 * duplicating the sequence logic and race condition handling.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-stores-backend/events
 */

import wixData from 'wix-data';
import { generateOrderId } from 'backend/orderId.web.js';

const SKU_PREFIX = 'WDSR';

/**
 * Triggered when a new product is created in Wix Stores.
 * Auto-assigns a SKU if the product doesn't have one.
 *
 * SKU format: WDSR-{INITIALS}-{BASE36_TIMESTAMP}
 * e.g. WDSR-BL-K4F2 for "Blue Leather Wallet"
 */
export async function wixStores_onProductCreated(event) {
  const product = event.entity || event;
  const productId = product._id || product.productId;

  if (!productId) return;

  try {
    // Re-fetch to get the full product (event payload may be partial)
    const existing = await wixData.get('Stores/Products', productId, { suppressAuth: true });
    if (!existing) return;

    // Skip if SKU already set
    if (existing.sku) return;

    // Generate SKU: PREFIX-INITIALS-TIMESTAMP_SUFFIX
    const words = (existing.name || '').split(/\s+/).filter(Boolean);
    const nameCode = words.length >= 2
      ? (words[0][0] + words[1][0]).toUpperCase()
      : (existing.name || 'XX').slice(0, 2).toUpperCase().padEnd(2, 'X');

    const timestamp = Date.now().toString(36).toUpperCase().slice(-4);
    const sku = `${SKU_PREFIX}-${nameCode}-${timestamp}`;

    await wixData.update('Stores/Products', {
      ...existing,
      sku,
    }, { suppressAuth: true });

    console.log(`[events] Auto-assigned SKU ${sku} to product ${productId} (${existing.name})`);
  } catch (err) {
    console.error(`[events] Failed to assign SKU to product ${productId}:`, err.message);
  }
}

/**
 * Triggered when a new order is placed.
 * Delegates to the shared generateOrderId() in orderId.web.js
 * which handles sequence numbering and race conditions.
 *
 * Passes memberId and buyerEmail so the OrderCustomIds collection
 * can be queried by member for the "My Orders" form/page.
 *
 * Also sets the Wix order customField to the WDSR number so it
 * appears in the Wix Owner App and native order emails.
 */
export async function wixEcom_onOrderCreated(event) {
  const order = event.entity || event;
  const orderId = order._id || order.orderId;

  if (!orderId) return;

  // Extract buyer metadata for member-based lookups
  const buyer = order.buyerInfo || {};
  const meta = {
    memberId: buyer.memberId || buyer.visitorId || '',
    buyerEmail: buyer.email || '',
  };

  try {
    const result = await generateOrderId(orderId, meta);
    console.log(`[events] Order ${orderId} → ${result.customOrderNumber}${result.alreadyExists ? ' (already existed)' : ''}`);

    // Set the WDSR number as the order's customField so it shows
    // in the Wix Owner App and native order confirmation emails.
    // This replaces the Wix native order number in customer-facing contexts.
    try {
      const orderRecord = await wixData.get('Stores/Orders', orderId, { suppressAuth: true });
      if (orderRecord) {
        await wixData.update('Stores/Orders', {
          ...orderRecord,
          customField: {
            title: 'Order ID',
            value: result.customOrderNumber,
          },
        }, { suppressAuth: true });
        console.log(`[events] Set customField on order ${orderId} → ${result.customOrderNumber}`);
      }
    } catch (cfErr) {
      // Non-critical — the WDSR is still in OrderCustomIds
      console.error(`[events] Failed to set customField on order ${orderId}:`, cfErr.message);
    }

  } catch (err) {
    console.error(`[events] Failed to assign custom order number to order ${orderId}:`, err.message);
  }
}
