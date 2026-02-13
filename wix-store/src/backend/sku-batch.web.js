// backend/sku-batch.web.js

import wixData from 'wix-data';
import wixStoresBackend from 'wix-stores-backend';
import { webMethod, Permissions } from 'wix-web-module';

// Same charset as orderId/events ΓÇö no 0/O/1/I
const CHARSET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";
const SKU_LENGTH = 8;

function makeRandomSku() {
  let sku = "";
  for (let i = 0; i < SKU_LENGTH; i++) {
    const index = Math.floor(Math.random() * CHARSET.length);
    sku += CHARSET.charAt(index);
  }
  return sku;
}

function makeUniqueSku(used) {
  let sku;
  let attempts = 0;
  do {
    sku = makeRandomSku();
    attempts++;
    if (attempts > 50) {
      throw new Error('Failed to generate unique SKU after 50 attempts');
    }
  } while (used.has(sku.toUpperCase()));
  used.add(sku.toUpperCase());
  return sku;
}

/**
 * For a single product: set variant SKUs as PRODUCTSKU-01, -02, ...
 * Returns count of variants updated.
 */
async function updateVariantSkusForProduct(product, overwriteVariants, usedSkus, dryRun) {
  const productId = product._id;
  const productSku = (product.sku || "").trim();

  if (!productSku || !product.manageVariants) {
    return 0;
  }

  const variantsResult = await wixData
    .query("Stores/Variants")
    .eq("productId", productId)
    .limit(100)
    .find();

  if (!variantsResult.items.length) {
    return 0;
  }

  const variantData = [];
  let index = 1;

  for (const variant of variantsResult.items) {
    const currentVariantSku = (variant.sku || "").trim();

    if (!overwriteVariants && currentVariantSku) {
      index++;
      continue;
    }

    const choices = variant.choices;
    let baseVariantSku = productSku + "-" + String(index).padStart(2, "0");

    let variantSku = baseVariantSku;
    let counter = 1;
    while (usedSkus.has(variantSku.toUpperCase())) {
      counter++;
      variantSku = baseVariantSku + "-" + counter;
    }
    usedSkus.add(variantSku.toUpperCase());

    variantData.push({ sku: variantSku, choices });
    index++;
  }

  if (variantData.length && !dryRun) {
    await wixStoresBackend.updateVariantData(productId, variantData);
  }

  return variantData.length;
}

async function getAllStoreProducts() {
  const all = [];
  let result = await wixData.query("Stores/Products").limit(100).find();
  all.push(...result.items);

  while (result.hasNext()) {
    result = await result.next();
    all.push(...result.items);
  }

  return all;
}

/**
 * Batch assign SKUs to all products.
 *
 * Options:
 *   overwrite  (bool)   ΓÇö false: only fill empty SKUs. true: replace all.
 *   dryRun     (bool)   ΓÇö true: preview changes without writing. Default false.
 *   prefix     (string) ΓÇö optional prefix for SKUs, e.g. "RG" ΓåÆ "RG-ABCD1234"
 *
 * Returns: { updated, skipped, errors, totalProducts, variantsUpdated, dryRun }
 */
export const assignSkusToAllProducts = webMethod(
  Permissions.Admin,
  async ({ overwrite = false, dryRun = false, prefix = '' } = {}) => {
    const products = await getAllStoreProducts();
    const totalProducts = products.length;

    // Collect existing SKUs for collision avoidance
    const usedSkus = new Set(
      products
        .map((p) => p.sku)
        .filter((s) => typeof s === "string" && s.trim() !== "")
        .map((s) => s.trim().toUpperCase())
    );

    const cleanPrefix = (prefix || '').trim().toUpperCase();
    const updated = [];
    const skipped = [];
    const errors = [];
    let variantsUpdated = 0;

    for (const p of products) {
      try {
        let productSku = (p.sku || "").trim();

        // 1) Product-level SKU
        if (!productSku || overwrite) {
          let newSku = makeUniqueSku(usedSkus);
          if (cleanPrefix) {
            newSku = cleanPrefix + "-" + newSku;
            usedSkus.add(newSku.toUpperCase());
          }

          if (!dryRun) {
            await wixStoresBackend.updateProductFields(p._id, { sku: newSku });
          }

          updated.push({
            id: p._id,
            name: p.name,
            oldSku: productSku || null,
            newSku: newSku,
          });

          productSku = newSku;
        } else {
          skipped.push({ id: p._id, name: p.name, sku: productSku });
        }

        // 2) Variant SKUs
        const vCount = await updateVariantSkusForProduct(
          { ...p, sku: productSku },
          overwrite,
          usedSkus,
          dryRun
        );
        variantsUpdated += vCount;
      } catch (err) {
        errors.push({
          id: p._id,
          name: p.name,
          error: err?.message || String(err),
        });
      }
    }

    return {
      dryRun,
      prefix: cleanPrefix || null,
      totalProducts,
      updated,
      skipped,
      errors,
      variantsUpdated,
      summary: `${updated.length} updated, ${skipped.length} skipped, ${errors.length} errors, ${variantsUpdated} variants${dryRun ? ' (DRY RUN ΓÇö no changes written)' : ''}`
    };
  }
);