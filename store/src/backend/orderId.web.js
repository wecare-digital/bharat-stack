/**
 * Custom Order ID Generator — WECARE.DIGITAL
 *
 * Generates custom order numbers with WD prefix (WECARE.DIGITAL).
 * Called from frontend, events, or automations to assign a human-readable order ID.
 *
 * Format: WD-YYYYMMDD-XXXX (e.g. WD-20260222-0042)
 *
 * The prefix is configurable — change PREFIX constant to rebrand.
 * Examples:
 *   WD-20260222-0042  (default — WECARE.DIGITAL)
 *   WCDO-20260222-0042  (WECARE.DIGITAL Order)
 *
 * Stores mapping in "OrderCustomIds" collection:
 *   { orderId, customOrderNumber, memberId, buyerEmail, _createdDate }
 *
 * The memberId and buyerEmail fields enable member-based order lookups
 * from the Wix Form / My Orders page without hitting the Wix eCommerce API.
 *
 * Race condition handling: If two concurrent calls generate the same sequence,
 * the insert will fail on the unique orderId. We catch that and retry with
 * an incremented sequence.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-web-module
 */

import { Permissions, webMethod } from 'wix-web-module';
import wixData from 'wix-data';

const PREFIX = 'WD';
const COLLECTION = 'OrderCustomIds';
const MAX_RETRIES = 3;

/**
 * Build a WD-YYYYMMDD-XXXX order number for a given sequence.
 */
function buildOrderNumber(seq) {
  const now = new Date();
  const datePart = [
    now.getFullYear(),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('');
  return `${PREFIX}-${datePart}-${String(seq).padStart(4, '0')}`;
}

/**
 * Get today's current count from the OrderCustomIds collection.
 */
async function getTodayCount() {
  const now = new Date();
  const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  return wixData.query(COLLECTION)
    .ge('_createdDate', todayStart)
    .count({ suppressAuth: true });
}

/**
 * Generate and persist a custom order number for a given Wix order ID.
 * Handles race conditions by retrying with incremented sequence on duplicate insert.
 *
 * Also stores memberId and buyerEmail for member-based order lookups.
 *
 * @param {string} orderId - The Wix eCommerce order ID
 * @param {{ memberId?: string, buyerEmail?: string }} meta - Optional buyer metadata
 * @returns {{ customOrderNumber: string, orderId: string }}
 */
export const generateOrderId = webMethod(
  Permissions.SiteMember,
  async (orderId, meta = {}) => {
    if (!orderId) throw new Error('orderId is required');

    const { memberId = '', buyerEmail = '' } = meta || {};

    // Check if already assigned (idempotent)
    const existing = await wixData.query(COLLECTION)
      .eq('orderId', orderId)
      .limit(1)
      .find({ suppressAuth: true });

    if (existing.items.length > 0) {
      // Backfill memberId/email if missing on existing record
      const record = existing.items[0];
      if ((!record.memberId && memberId) || (!record.buyerEmail && buyerEmail)) {
        try {
          await wixData.update(COLLECTION, {
            ...record,
            memberId: record.memberId || memberId,
            buyerEmail: record.buyerEmail || buyerEmail,
          }, { suppressAuth: true });
        } catch { /* non-critical — skip */ }
      }
      return {
        customOrderNumber: record.customOrderNumber,
        orderId,
        alreadyExists: true,
      };
    }

    // Generate with retry for race conditions
    let lastError;
    for (let attempt = 0; attempt < MAX_RETRIES; attempt++) {
      const count = await getTodayCount();
      const seq = count + 1 + attempt; // offset by attempt to avoid same seq on retry
      const customOrderNumber = buildOrderNumber(seq);

      try {
        await wixData.insert(COLLECTION, {
          orderId,
          customOrderNumber,
          memberId,
          buyerEmail,
        }, { suppressAuth: true });

        return { customOrderNumber, orderId };
      } catch (err) {
        lastError = err;
        // If it's a duplicate orderId (already inserted by concurrent call), return that
        const recheck = await wixData.query(COLLECTION)
          .eq('orderId', orderId)
          .limit(1)
          .find({ suppressAuth: true });
        if (recheck.items.length > 0) {
          return {
            customOrderNumber: recheck.items[0].customOrderNumber,
            orderId,
            alreadyExists: true,
          };
        }
        // Otherwise retry with next sequence
      }
    }

    throw new Error(`Failed to generate order ID after ${MAX_RETRIES} attempts: ${lastError?.message}`);
  }
);

/**
 * Look up a custom order number by Wix order ID.
 * @param {string} orderId
 * @returns {string|null}
 */
export const getCustomOrderNumber = webMethod(
  Permissions.SiteMember,
  async (orderId) => {
    if (!orderId) return null;
    const result = await wixData.query(COLLECTION)
      .eq('orderId', orderId)
      .limit(1)
      .find({ suppressAuth: true });

    return result.items.length > 0 ? result.items[0].customOrderNumber : null;
  }
);

/**
 * Look up a Wix order ID by custom order number.
 * @param {string} customOrderNumber - e.g. "WD-20260222-0042"
 * @returns {string|null}
 */
export const getOrderByCustomNumber = webMethod(
  Permissions.SiteMember,
  async (customOrderNumber) => {
    if (!customOrderNumber) return null;
    const result = await wixData.query(COLLECTION)
      .eq('customOrderNumber', customOrderNumber)
      .limit(1)
      .find({ suppressAuth: true });

    return result.items.length > 0 ? result.items[0].orderId : null;
  }
);
