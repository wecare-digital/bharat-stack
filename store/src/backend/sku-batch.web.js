/**
 * Batch SKU Operations — WECARE.DIGITAL
 *
 * Web module for bulk SKU management:
 *   - Assign SKUs to products missing them
 *   - Re-prefix SKUs (e.g. WD-001 → WDSR-001)
 *   - Dry-run mode to preview changes before committing
 *
 * SKU format: {PREFIX}-{CATEGORY_CODE}-{SEQ}
 *   e.g. WDSR-EL-001, WDSR-CL-042
 *
 * Uses bulkUpdate for batch writes instead of sequential updates.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-web-module
 */

import { Permissions, webMethod } from 'wix-web-module';
import wixData from 'wix-data';

const DEFAULT_PREFIX = 'WDSR';
const PRODUCTS_COLLECTION = 'Stores/Products';
const BATCH_SIZE = 50; // Wix bulkUpdate limit

/**
 * Generate a 2-char code from a product name.
 * Takes first letter of first two words, or first two chars.
 */
function nameToCode(name) {
  if (!name) return 'XX';
  const words = name.split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[1][0]).toUpperCase();
  }
  return name.slice(0, 2).toUpperCase().padEnd(2, 'X');
}

/**
 * Assign SKUs to all products that don't have one.
 *
 * The sequence counter is global across the batch (not per-page),
 * so SKUs are sequential: WDSR-BL-001, WDSR-RD-002, etc.
 *
 * @param {{ prefix?: string, dryRun?: boolean }} options
 * @returns {{ processed: number, skipped: number, dryRun: boolean, assignments: Array }}
 */
export const assignMissingSKUs = webMethod(
  Permissions.Admin,
  async ({ prefix = DEFAULT_PREFIX, dryRun = true } = {}) => {
    const assignments = [];
    let globalSeq = 0;
    let skipped = 0;
    let offset = 0;

    // First pass: count existing SKUs to start sequence after them
    const totalWithSku = await wixData.query(PRODUCTS_COLLECTION)
      .isNotEmpty('sku')
      .count({ suppressAuth: true });
    globalSeq = totalWithSku;

    while (true) {
      const result = await wixData.query(PRODUCTS_COLLECTION)
        .limit(100)
        .skip(offset)
        .ascending('_createdDate')
        .find({ suppressAuth: true });

      if (result.items.length === 0) break;

      const toUpdate = [];

      for (const product of result.items) {
        if (product.sku) {
          skipped++;
          continue;
        }

        globalSeq++;
        const code = nameToCode(product.name);
        const newSku = `${prefix}-${code}-${String(globalSeq).padStart(3, '0')}`;

        assignments.push({
          productId: product._id,
          name: product.name,
          oldSku: '(none)',
          newSku,
        });

        if (!dryRun) {
          toUpdate.push({ ...product, sku: newSku });
        }
      }

      // Bulk update in batches
      if (!dryRun && toUpdate.length > 0) {
        for (let i = 0; i < toUpdate.length; i += BATCH_SIZE) {
          const batch = toUpdate.slice(i, i + BATCH_SIZE);
          await wixData.bulkUpdate(PRODUCTS_COLLECTION, batch, { suppressAuth: true });
        }
      }

      offset += 100;
      if (result.items.length < 100) break;
    }

    return {
      processed: assignments.length,
      skipped,
      dryRun,
      assignments,
    };
  }
);

/**
 * Re-prefix existing SKUs from one prefix to another.
 *
 * @param {{ oldPrefix: string, newPrefix?: string, dryRun?: boolean }} options
 * @returns {{ updated: number, skipped: number, dryRun: boolean, changes: Array }}
 */
export const reprefixSKUs = webMethod(
  Permissions.Admin,
  async ({ oldPrefix, newPrefix = DEFAULT_PREFIX, dryRun = true }) => {
    if (!oldPrefix) throw new Error('oldPrefix is required');
    if (oldPrefix === newPrefix) throw new Error('oldPrefix and newPrefix must be different');

    const changes = [];
    let skipped = 0;
    let offset = 0;

    while (true) {
      const result = await wixData.query(PRODUCTS_COLLECTION)
        .startsWith('sku', oldPrefix)
        .limit(100)
        .skip(offset)
        .find({ suppressAuth: true });

      if (result.items.length === 0) break;

      const toUpdate = [];

      for (const product of result.items) {
        const oldSku = product.sku || '';
        if (!oldSku.startsWith(oldPrefix)) {
          skipped++;
          continue;
        }

        const newSku = newPrefix + oldSku.slice(oldPrefix.length);
        changes.push({
          productId: product._id,
          name: product.name,
          oldSku,
          newSku,
        });

        if (!dryRun) {
          toUpdate.push({ ...product, sku: newSku });
        }
      }

      // Bulk update
      if (!dryRun && toUpdate.length > 0) {
        for (let i = 0; i < toUpdate.length; i += BATCH_SIZE) {
          const batch = toUpdate.slice(i, i + BATCH_SIZE);
          await wixData.bulkUpdate(PRODUCTS_COLLECTION, batch, { suppressAuth: true });
        }
      }

      offset += 100;
      if (result.items.length < 100) break;
    }

    return { updated: changes.length, skipped, dryRun, changes };
  }
);
