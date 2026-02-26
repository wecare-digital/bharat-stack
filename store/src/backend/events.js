/**
 * Wix Events — WECARE.DIGITAL
 *
 * Auto-triggered backend event handlers.
 *
 * Events:
 *   - wixStores_onProductCreated: Auto-assign SKU to new products
 *   - wixEcom_onOrderApproved: Generate custom order ID (WD-ORD prefix)
 *
 * IMPORTANT: events.js does NOT support dynamic exports or
 * webMethod() imports. That's why we import from orderId-helpers.js
 * (plain .js) instead of orderId.web.js.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-stores-backend/events
 */

import wixStoresBackend from 'wix-stores-backend';
import wixData from 'wix-data';
import { createOrGetOrderId } from 'backend/orderId-helpers';

const CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const SKU_LENGTH = 8;
const MAX_COLLISION_RETRIES = 10;

function makeRandomSku() {
  let sku = "";
  for (let i = 0; i < SKU_LENGTH; i++) {
    const index = Math.floor(Math.random() * CHARSET.length);
    sku += CHARSET.charAt(index);
  }
  return sku;
}

async function getExistingSkus() {
  const skus = new Set();
  let result = await wixData.query("Stores/Products").limit(100).find();
  result.items.forEach(p => {
    if (p.sku) skus.add(p.sku.trim().toUpperCase());
  });
  while (result.hasNext()) {
    result = await result.next();
    result.items.forEach(p => {
      if (p.sku) skus.add(p.sku.trim().toUpperCase());
    });
  }
  return skus;
}

function makeUniqueSku(existingSkus) {
  let attempts = 0;
  let sku;
  do {
    sku = makeRandomSku();
    attempts++;
    if (attempts > MAX_COLLISION_RETRIES) {
      console.error(`[events] Failed to generate unique SKU after ${MAX_COLLISION_RETRIES} attempts`);
      return sku;
    }
  } while (existingSkus.has(sku.toUpperCase()));
  existingSkus.add(sku.toUpperCase());
  return sku;
}

async function updateVariantSkusForProduct(productId, productSku) {
  try {
    const product = await wixData.get("Stores/Products", productId);
    if (!product.manageVariants) return;

    const variantsResult = await wixData
      .query("Stores/Variants")
      .eq("productId", productId)
      .limit(100)
      .find();

    if (!variantsResult.items.length) return;

    const variantData = [];
    let index = 1;
    for (const variant of variantsResult.items) {
      const choices = variant.choices;
      const variantSku = productSku + "-" + String(index).padStart(2, "0");
      variantData.push({ sku: variantSku, choices });
      index++;
    }

    if (variantData.length) {
      await wixStoresBackend.updateVariantData(productId, variantData);
      console.log(`[events] Set ${variantData.length} variant SKUs for product ${productId}`);
    }
  } catch (err) {
    console.error(`[events] Failed to update variant SKUs for product ${productId}:`, err?.message || err);
  }
}

/**
 * Runs automatically whenever a new product is created in Wix Stores.
 */
export async function wixStores_onProductCreated(event) {
  const productId = event._id;
  try {
    const existingSkus = await getExistingSkus();
    const productSku = makeUniqueSku(existingSkus);
    await wixStoresBackend.updateProductFields(productId, { sku: productSku });
    console.log(`[events] Assigned SKU ${productSku} to new product ${productId}`);
    await updateVariantSkusForProduct(productId, productSku);
  } catch (err) {
    console.error(`[events] Failed to assign SKU for product ${productId}:`, err?.message || err);
  }
}

/**
 * Triggered when a new order is approved (paid).
 * Generates WD-ORD number and stores in OrderIDs + OrderCustomIds.
 * Also sets the Wix order customField so it shows in Owner App.
 */
export async function wixEcom_onOrderApproved(event) {
  const order = event.entity || event;
  const orderId = order._id || order.orderId;
  if (!orderId) return;

  const buyer = order.buyerInfo || {};
  const orderDate = order._createdDate || order._dateCreated || new Date();

  try {
    const wdOrderId = await createOrGetOrderId({
      wixOrderId: orderId,
      memberId: buyer.memberId || buyer.visitorId || '',
      orderNumber: order.number ? String(order.number) : '',
      buyerEmail: buyer.email || '',
      buyerPhone: buyer.phone || '',
      totalAmount: '',
      currency: order.currency || '',
      productsSummary: '',
      orderDate,
    });

    console.log(`[events] Order ${orderId} → ${wdOrderId}`);

    // Set customField on the order so WD number shows in Wix Owner App
    try {
      const orderRecord = await wixData.get('Stores/Orders', orderId, { suppressAuth: true });
      if (orderRecord) {
        await wixData.update('Stores/Orders', {
          ...orderRecord,
          customField: { title: 'Order ID', value: wdOrderId },
        }, { suppressAuth: true });
        console.log(`[events] Set customField on order ${orderId} → ${wdOrderId}`);
      }
    } catch (cfErr) {
      console.error(`[events] Failed to set customField on order ${orderId}:`, cfErr?.message);
    }
  } catch (err) {
    console.error(`[events] Failed to assign WD order number to order ${orderId}:`, err?.message || err);
  }
}
