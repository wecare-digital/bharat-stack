/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Auto-populates the Order ID dropdown with the logged-in
 * member's WD-ORD numbers. Uses Wix Form (#form1).
 *
 * Dropdown field key: dropdown_f78d
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(async () => {
  const dd = $w('#dropdown_f78d');

  let email = null;
  try {
    const member = await currentMember.getMember({ fieldsets: ['FULL'] });
    email = member?.loginEmail
      || (member?.contactDetails?.emails && member.contactDetails.emails[0])
      || null;
    console.log('[submitRequest] member email:', email);
  } catch (e) {
    console.error('[submitRequest] getMember failed:', e);
  }

  if (!email) {
    dd.options = [{ value: '', label: 'Please log in to see your orders' }];
    dd.selectedIndex = 0;
    dd.disable();
    return;
  }

  // Loading state
  dd.options = [{ value: '', label: 'Loading your orders...' }];
  dd.selectedIndex = 0;

  try {
    const orderIds = await getMyOrderIdList(email);
    console.log('[submitRequest] orderIds:', JSON.stringify(orderIds));

    if (orderIds && orderIds.length > 0) {
      dd.options = [
        { value: '', label: 'Select your order...' },
        ...orderIds,
      ];
    } else {
      dd.options = [{ value: '', label: 'No orders found' }];
    }
    dd.selectedIndex = 0;
    dd.enable();
  } catch (err) {
    console.error('[submitRequest] getMyOrderIdList error:', err);
    dd.options = [{ value: '', label: 'Error loading orders' }];
    dd.enable();
  }
});
