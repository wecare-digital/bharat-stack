/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Wix Form (#form1) with field key "order_id_1" (text input).
 * On page load, fetches logged-in member's WD-ORD IDs and
 * auto-fills the form field using setFieldValues().
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(async () => {
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
    console.log('[submitRequest] No email — user not logged in');
    return;
  }

  try {
    const orderIds = await getMyOrderIdList(email);
    console.log('[submitRequest] orderIds count:', orderIds?.length);

    if (orderIds && orderIds.length > 0) {
      // Auto-fill the form field with the most recent order ID
      $w('#form1').setFieldValues({
        order_id_1: orderIds[0].value,
      });
      console.log('[submitRequest] Set order_id_1 to:', orderIds[0].value);
    }
  } catch (e) {
    console.error('[submitRequest] Failed:', e);
  }
});
