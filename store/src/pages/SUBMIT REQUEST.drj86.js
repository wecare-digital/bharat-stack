/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Wix Form V2 with field key "order_id_1".
 * Auto-fills the order ID field for logged-in members.
 *
 * Uses setFieldValues() — the official WixFormsV2 API.
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(async () => {
  // Debug: log all form field keys to find the right ones
  try {
    const vals = $w('#form1').getFieldValues();
    console.log('[submitRequest] form1 field values:', JSON.stringify(vals));
  } catch (e) {
    console.error('[submitRequest] form1 not found or getFieldValues failed:', e);
    // Try the long ID
    try {
      const vals2 = $w('#371Ee199389C4A93849Ee35B8A15B7Ca1').getFieldValues();
      console.log('[submitRequest] long ID field values:', JSON.stringify(vals2));
    } catch (e2) {
      console.error('[submitRequest] long ID also failed:', e2);
    }
  }

  // Get member email
  let email = null;
  try {
    const member = await currentMember.getMember({ fieldsets: ['FULL'] });
    email = member?.loginEmail
      || (member?.contactDetails?.emails && member.contactDetails.emails[0])
      || null;
    console.log('[submitRequest] email:', email);
  } catch (e) {
    console.error('[submitRequest] getMember error:', e);
  }

  if (!email) {
    console.log('[submitRequest] No email — not logged in');
    return;
  }

  // Fetch order IDs
  let orderIds = [];
  try {
    orderIds = await getMyOrderIdList(email);
    console.log('[submitRequest] orderIds:', JSON.stringify(orderIds));
  } catch (e) {
    console.error('[submitRequest] getMyOrderIdList error:', e);
    return;
  }

  if (!orderIds || orderIds.length === 0) {
    console.log('[submitRequest] No orders found');
    return;
  }

  // Set the field value using WixFormsV2 API
  const orderId = orderIds[0].value;
  try {
    $w('#form1').setFieldValues({ order_id_1: orderId });
    console.log('[submitRequest] setFieldValues done:', orderId);
  } catch (e) {
    console.error('[submitRequest] setFieldValues on #form1 failed:', e);
    // Fallback: try long form ID
    try {
      $w('#371Ee199389C4A93849Ee35B8A15B7Ca1').setFieldValues({ order_id_1: orderId });
      console.log('[submitRequest] setFieldValues on long ID done:', orderId);
    } catch (e2) {
      console.error('[submitRequest] setFieldValues on long ID also failed:', e2);
    }
  }
});
