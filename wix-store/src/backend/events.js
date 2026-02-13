// backend/events.js

import wixStoresBackend from 'wix-stores-backend';
import wixData from 'wix-data';

// Same charset as orderId.web.js — no 0/O/1/I to avoid confusion
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

/**
 * Query all existing product SKUs to avoid collisions.
 */
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

/**
 * Generate a unique SKU that doesn't collide with existing ones.
 */
function makeUniqueSku(existingSkus) {
  let attempts = 0;
  let sku;
  do {
    sku = makeRandomSku();
    attempts++;
    if (attempts > MAX_COLLISION_RETRIES) {
      console.error(`[events] Failed to generate unique SKU after ${MAX_COLLISION_RETRIES} attempts`);
      return sku; // return last attempt rather than failing silently
    }
  } while (existingSkus.has(sku.toUpperCase()));
  existingSkus.add(sku.toUpperCase());
  return sku;
}

/**
 * Set variant SKUs for a product based on the product SKU.
 * Variant SKUs = PRODUCTSKU-01, PRODUCTSKU-02, ...
 */
async function updateVariantSkusForProduct(productId, productSku) {
  try {
    const product = await wixData.get("Stores/Products", productId);

    if (!product.manageVariants) {
      return;
    }

    const variantsResult = await wixData
      .query("Stores/Variants")
      .eq("productId", productId)
      .limit(100)
      .find();

    if (!variantsResult.items.length) {
      return;
    }

    const variantData = [];
    let index = 1;

    for (const variant of variantsResult.items) {
      const choices = variant.choices;
      const variantSku =
        productSku + "-" + String(index).padStart(2, "0");

      variantData.push({
        sku: variantSku,
        choices,
      });

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
 * - Generates collision-free product SKU
 * - Generates variant SKUs if the product has managed variants
 */
export async function wixStores_onProductCreated(event) {
  const productId = event._id;

  try {
    // 1) Gather existing SKUs for collision avoidance
    const existingSkus = await getExistingSkus();

    // 2) Product-level SKU
    const productSku = makeUniqueSku(existingSkus);

    await wixStoresBackend.updateProductFields(productId, {
      sku: productSku,
    });

    console.log(`[events] Assigned SKU ${productSku} to new product ${productId}`);

    // 3) Variant SKUs (if variants exist & are managed)
    await updateVariantSkusForProduct(productId, productSku);
  } catch (err) {
    console.error(`[events] Failed to assign SKU for product ${productId}:`, err?.message || err);
  }
}
