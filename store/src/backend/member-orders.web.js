/**
 * Member Orders — WECARE.DIGITAL
 *
 * Web module for logged-in members to fetch their own orders.
 * Used by the "My Orders" Wix Form / page to display order history
 * using only the WD custom order ID (Wix native order number is hidden).
 *
 * Flow:
 *   1. Logged-in user opens "My Orders" page/form
 *   2. Page code calls getMyOrders() with the current member's ID
 *   3. This module queries OrderCustomIds by memberId
 *   4. For each match, fetches the full order from Stores/Orders
 *   5. Returns enriched orders with WD number as the primary ID
 *
 * The Wix native order number (order.number) is stripped from the response
 * so it never reaches the frontend.
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-web-module
 */

import { Permissions, webMethod } from 'wix-web-module';
import wixData from 'wix-data';

const ORDER_IDS_COLLECTION = 'OrderCustomIds';
const ORDERS_COLLECTION = 'Stores/Orders';

/**
 * Strip Wix native order number from an order object.
 * We only expose the WD custom order ID.
 */
function stripNativeOrderNumber(order) {
  if (!order) return order;
  const cleaned = { ...order };
  delete cleaned.number; // Wix native sequential number
  return cleaned;
}

/**
 * Get all orders for the currently logged-in member.
 * Returns orders with WD custom order ID as the primary identifier.
 * Wix native order number is stripped.
 *
 * @param {string} memberId - The Wix member ID (from currentMember.getMember())
 * @param {{ limit?: number, offset?: number }} options
 * @returns {{ orders: Array, totalCount: number }}
 */
export const getMyOrders = webMethod(
  Permissions.SiteMember,
  async (memberId, { limit = 20, offset = 0 } = {}) => {
    if (!memberId) throw new Error('memberId is required');

    // Query OrderCustomIds by memberId
    const mappings = await wixData.query(ORDER_IDS_COLLECTION)
      .eq('memberId', memberId)
      .descending('_createdDate')
      .limit(limit)
      .skip(offset)
      .find({ suppressAuth: true });

    if (mappings.items.length === 0) {
      return { orders: [], totalCount: mappings.totalCount };
    }

    // Fetch full order details for each mapping
    const orders = [];
    for (const mapping of mappings.items) {
      try {
        const order = await wixData.get(ORDERS_COLLECTION, mapping.orderId, { suppressAuth: true });
        if (order) {
          const cleaned = stripNativeOrderNumber(order);
          cleaned.customOrderNumber = mapping.customOrderNumber;
          cleaned.orderDisplayId = mapping.customOrderNumber; // Primary display ID
          orders.push(cleaned);
        }
      } catch {
        // Order may have been deleted — still show the mapping
        orders.push({
          _id: mapping.orderId,
          customOrderNumber: mapping.customOrderNumber,
          orderDisplayId: mapping.customOrderNumber,
          _status: 'order_not_found',
        });
      }
    }

    return { orders, totalCount: mappings.totalCount };
  }
);

/**
 * Get a single order by WD custom order number.
 * Only returns the order if it belongs to the requesting member.
 * Wix native order number is stripped.
 *
 * @param {string} memberId - The Wix member ID
 * @param {string} customOrderNumber - e.g. "WD-ORD-20260222-0042"
 * @returns {object|null}
 */
export const getMyOrderByNumber = webMethod(
  Permissions.SiteMember,
  async (memberId, customOrderNumber) => {
    if (!memberId || !customOrderNumber) return null;

    const mapping = await wixData.query(ORDER_IDS_COLLECTION)
      .eq('customOrderNumber', customOrderNumber)
      .eq('memberId', memberId)
      .limit(1)
      .find({ suppressAuth: true });

    if (mapping.items.length === 0) return null;

    try {
      const order = await wixData.get(ORDERS_COLLECTION, mapping.items[0].orderId, { suppressAuth: true });
      if (!order) return null;

      const cleaned = stripNativeOrderNumber(order);
      cleaned.customOrderNumber = customOrderNumber;
      cleaned.orderDisplayId = customOrderNumber;
      return cleaned;
    } catch {
      return null;
    }
  }
);

/**
 * Get order count for a member (for badge/notification display).
 *
 * @param {string} memberId
 * @returns {number}
 */
export const getMyOrderCount = webMethod(
  Permissions.SiteMember,
  async (memberId) => {
    if (!memberId) return 0;
    return wixData.query(ORDER_IDS_COLLECTION)
      .eq('memberId', memberId)
      .count({ suppressAuth: true });
  }
);
