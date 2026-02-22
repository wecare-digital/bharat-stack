/**
 * Custom Order ID Generator — WECARE.DIGITAL
 *
 * Generates custom order numbers with WD-ORD prefix (WECARE.DIGITAL).
 * Called from frontend, events, or automations to assign a human-readable order ID.
 *
 * Format: WD-ORD-{UUID8}-{DD-MM-YYYY}-{HH:MM:SS}-IST
 *   e.g. WD-ORD-A3F7B2C1-22-02-2026-17:43:01-IST
 *
 * The prefix is configurable — change PREFIX constant to rebrand.
 * Example: WD-ORD-A3F7B2C1-22-02-2026-17:43:01-IST  (WECARE.DIGITAL Order)
 *
 * Stores mapping in "OrderCustomIds" collection:
 *   { orderId, customOrderNumber, memberId, buyerEmail, _createdDate }
 *
 * The memberId and buyerEmail fields enable member-based order lookups
 * from the Wix Form / My Orders page without hitting the Wix eCommerce API.
 *
 * Race condition handling: UUID-based IDs eliminate sequence conflicts.
 * If two concurrent calls happen, each gets a unique UUID.
 * The insert will only fail if the same orderId is inserted twice,
 * in which case we return the existing record.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-web-module
 */

import { Permissions, webMethod } from 'wix-web-module';
import wixData from 'wix-data';

const PREFIX = 'WD-ORD';
const COLLECTION = 'OrderCustomIds';

/**
 * Build a WD-ORD-{UUID8}-{DD-MM-YYYY}-{HH:MM:SS}-IST order number.
 * Uses IST timezone (UTC+5:30).
 */
function buildOrderNumber() {
  // IST = UTC + 5:30
  const now = new Date();
  const istOffset = 5.5 * 60 * 60 * 1000; // 5h30m in ms
  const ist = new Date(now.getTime() + istOffset + now.getTimezoneOffset() * 60 * 1000);

  const dd = String(ist.getDate()).padStart(2, '0');
  const mm = String(ist.getMonth() + 1).padStart(2, '0');
  const yyyy = ist.getFullYear();
  const hh = String(ist.getHours()).padStart(2, '0');
  const min = String(ist.getMinutes()).padStart(2, '0');
  const ss = String(ist.getSeconds()).padStart(2, '0');

  // 8-char hex UUID
  const uid = Array.from({ length: 8 }, () =>
    Math.floor(Math.random() * 16).toString(16)
  ).join('').toUpperCase();

  return `${PREFIX}-${uid}-${dd}-${mm}-${yyyy}-${hh}:${min}:${ss}-IST`;
}

/**
 * Generate UUID-based order number (no sequence conflicts).
 * Generate and persist a custom order number for a given Wix order ID.
 * Uses UUID-based format so no sequence conflicts possible.
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

    // Generate UUID-based order number (no sequence conflicts)
    const customOrderNumber = buildOrderNumber();

    try {
      await wixData.insert(COLLECTION, {
        orderId,
        customOrderNumber,
        memberId,
        buyerEmail,
      }, { suppressAuth: true });

      return { customOrderNumber, orderId };
    } catch (err) {
      // If insert fails (duplicate orderId from concurrent call), return existing
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
      throw new Error(`Failed to generate order ID: ${err?.message}`);
    }
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
 * @param {string} customOrderNumber - e.g. "WD-ORD-A3F7B2C1-22-02-2026-17:43:01-IST"
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
