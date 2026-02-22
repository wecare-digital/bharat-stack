/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Wix Form (#form1) with input field "order_id_1" inside it.
 * On page load, auto-populates the input with the logged-in
 * member's WD-ORD IDs so they can pick one.
 *
 * The form handles its own submission natively.
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

let _orderIds = [];

$w.onReady(async () => {
  let email = null;
  try {
    const member = await currentMember.getMember({ fieldsets: ['FULL'] });
    email = member?.loginEmail
      || (member?.contactDetails?.emails && member.contactDetails.emails[0])
      || null;
  } catch (e) {
    console.error('[submitRequest] getMember error:', e);
  }

  if (!email) return;

  try {
    _orderIds = await getMyOrderIdList(email);
  } catch (e) {
    console.error('[submitRequest] getMyOrderIdList error:', e);
    return;
  }

  if (!_orderIds || _orderIds.length === 0) return;

  // Pre-fill with most recent order ID
  try {
    $w('#order_id_1').value = _orderIds[0].value;
  } catch (e) {
    console.error('[submitRequest] Could not set order_id_1:', e);
  }

  // As user types, filter and suggest matching order IDs
  try {
    $w('#order_id_1').onInput((event) => {
      const typed = (event.target.value || '').toUpperCase();
      if (typed.length < 2) return;

      const match = _orderIds.find(o => o.value.toUpperCase().includes(typed));
      if (match && match.value.toUpperCase() !== typed) {
        // Don't override while they're still typing — just log suggestion
        console.log('[submitRequest] Suggestion:', match.value);
      }
    });
  } catch (e) {
    // onInput may not be available on all field types
  }
});
