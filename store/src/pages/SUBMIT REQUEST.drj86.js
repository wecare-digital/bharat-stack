/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Wix Form V2 with text input field key "order_id_1".
 * Auto-fills with the logged-in member's most recent WD-ORD number.
 *
 * Form fields (from DOM):
 *   - dropdown_f78d: dropdown "Order ID" (can't set options via code — remove this)
 *   - order_id_1: text input "Order ID" (we auto-fill this)
 *   - submit button
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(async () => {
  console.log('[submitRequest] Page ready');

  // Find the form element
  let form = null;
  const formIds = ['#form1', '#form2', '#wixForms1'];
  for (const id of formIds) {
    try {
      const f = $w(id);
      if (f && typeof f.setFieldValues === 'function') {
        form = f;
        console.log('[submitRequest] Found form:', id);
        break;
      }
    } catch (e) { /* not this ID */ }
  }

  if (!form) {
    console.error('[submitRequest] No form element found');
    return;
  }

  // Debug: log current field values to see all field keys
  try {
    const vals = form.getFieldValues();
    console.log('[submitRequest] Field keys:', JSON.stringify(vals));
  } catch (e) {
    console.error('[submitRequest] getFieldValues failed:', e);
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
    return;
  }

  if (!email) {
    console.log('[submitRequest] Not logged in');
    return;
  }

  // Fetch order IDs
  let orderIds = [];
  try {
    orderIds = await getMyOrderIdList(email);
    console.log('[submitRequest] Orders found:', orderIds?.length);
  } catch (e) {
    console.error('[submitRequest] getMyOrderIdList error:', e);
    return;
  }

  if (!orderIds || orderIds.length === 0) {
    console.log('[submitRequest] No orders');
    return;
  }

  // Auto-fill the text input with most recent order ID
  const orderId = orderIds[0].value;
  try {
    form.setFieldValues({ order_id_1: orderId });
    console.log('[submitRequest] Set order_id_1:', orderId);
  } catch (e) {
    console.error('[submitRequest] setFieldValues failed:', e);
  }

  // Also try setting the dropdown value (may or may not work)
  try {
    form.setFieldValues({ dropdown_f78d: orderId });
    console.log('[submitRequest] Set dropdown_f78d:', orderId);
  } catch (e) {
    // Dropdown may not accept programmatic values
  }
});
