/**
 * SUBMIT REQUEST Page (a8s2j) — WECARE.DIGITAL
 * Fallback: same logic as masterPage.js in case page code runs.
 *
 * NOTE: Wix may not pull this from Git (one-way sync for new pages),
 * but we keep it in sync as a safety net.
 *
 * - Populates #dropdown_sr with ALL member order IDs
 * - Sets #form1 order_id_1 to latest (or URL param)
 * - Wires dropdown change → form field update
 */

import wixLocationFrontend from 'wix-location-frontend';
import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(function () {
  fillSubmitRequestForm();
});

function fillSubmitRequestForm() {
  console.log('[SR-a8s] fillSubmitRequestForm running');

  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) { console.log('[SR-a8s] No member'); return null; }
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      if (!email) { console.log('[SR-a8s] No email'); return null; }
      console.log('[SR-a8s] Email:', email);
      return getMyOrderIdList(email);
    })
    .then(function (orderIds) {
      if (!orderIds || orderIds.length === 0) {
        console.log('[SR-a8s] No orders found');
        return;
      }
      console.log('[SR-a8s] Orders:', orderIds.length);

      // Populate dropdown with all order IDs
      var dropdownOptions = orderIds.map(function (o) {
        return { label: o.label, value: o.value };
      });

      try {
        $w('#dropdown_sr').options = dropdownOptions;
        console.log('[SR-a8s] Dropdown populated:', dropdownOptions.length);
      } catch (e) { console.error('[SR-a8s] Dropdown populate failed:', e); }

      // Check URL param — pre-select that order
      var query = wixLocationFrontend.query || {};
      var urlOrderId = query.orderId || '';
      var selectedId = urlOrderId || orderIds[0].value;

      try {
        $w('#dropdown_sr').value = selectedId;
      } catch (e) { console.error('[SR-a8s] Dropdown select failed:', e); }

      try {
        $w('#form1').setFieldValues({ order_id_1: selectedId });
        console.log('[SR-a8s] Form set:', selectedId);
      } catch (e) { console.error('[SR-a8s] Form set failed:', e); }

      // Wire dropdown change → update form field
      try {
        $w('#dropdown_sr').onChange(function (event) {
          var val = event.target.value;
          console.log('[SR-a8s] Dropdown changed:', val);
          try {
            $w('#form1').setFieldValues({ order_id_1: val });
          } catch (e2) { console.error('[SR-a8s] Form update failed:', e2); }
        });
      } catch (e) { console.error('[SR-a8s] onChange wire failed:', e); }
    })
    .catch(function (err) {
      console.error('[SR-a8s] Error:', err);
    });
}
