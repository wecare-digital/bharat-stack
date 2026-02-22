/**
 * Custom Order ID Web Module — WECARE.DIGITAL
 *
 * Web method wrappers for frontend → backend calls.
 * Delegates to orderId-helpers.js for the actual logic.
 *
 * Format: WD-ORD- {UUID8} -{DD-MM-YYYY} - {HH:MM:SS}-IST
 *
 * Docs: https://dev.wix.com/docs/velo/apis/wix-web-module
 */

import { Permissions, webMethod } from 'wix-web-module';
import {
  createOrGetOrderId as _createOrGetOrderId,
  getMemberOrdersPaged as _getMemberOrdersPaged,
} from 'backend/orderId-helpers';

/**
 * Create or fetch ORDER ID for order (called from Thank You page / frontend).
 */
export const createOrGetOrderId = webMethod(
  Permissions.Anyone,
  async (payload) => _createOrGetOrderId(payload)
);

/**
 * Paged list of orders for a member (called from My Orders page / frontend).
 */
export const getMemberOrdersPaged = webMethod(
  Permissions.Anyone,
  async (payload) => _getMemberOrdersPaged(payload)
);
