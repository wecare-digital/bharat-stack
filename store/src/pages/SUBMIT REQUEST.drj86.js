/**
 * SUBMIT REQUEST Page — WECARE.DIGITAL
 *
 * Auto-populates the Order ID dropdown (#dropdown_f78d) with
 * the logged-in member's WD-ORD numbers. No submit button needed.
 */

import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(async () => {
  const dd = $w('#dropdown_f78d');

  let member = null;
  try {
    member = await currentMember.getMember({ fieldsets: ['FULL'] });
  } catch { /* not logged in */ }

  if (!member) {
    dd.options = [{ value: '', label: 'Please log in to see your orders' }];
    dd.selectedIndex = 0;
    dd.disable();
    return;
  }

  const email = member.loginEmail || member.contactDetails?.emails?.[0] || '';

  if (!email) {
    dd.options = [{ value: '', label: 'No email found for your account' }];
    dd.selectedIndex = 0;
    dd.disable();
    return;
  }

  // Loading state
  dd.options = [{ value: '', label: 'Loading your orders...' }];
  dd.selectedIndex = 0;

  try {
    const orderIds = await getMyOrderIdList(email);
    if (orderIds.length > 0) {
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
    console.error('[submitRequest] Failed to load orders:', err);
    dd.options = [{ value: '', label: 'Failed to load orders' }];
  }
});
