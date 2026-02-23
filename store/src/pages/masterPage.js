/**************************************************************
 * masterPage.js
 * Site-wide bootstrap: hygiene + backend-driven SEO + lite ops
 * + Submit Request form auto-fill (order ID)
 **************************************************************/
import { initHygiene } from 'public/site-hygiene.js';
import { installSiteBootstrap } from 'public/global-apply.js';
import { installSeoBridge } from 'public/seo-bridge.js';
import { runOpsLite } from 'public/ops-lite.js';
import wixLocationFrontend from 'wix-location-frontend';
import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(function () {
  // 1) Hygiene
  initHygiene({
    useCanonicalize : true,
    defaultAlt      : 'WECARE.DIGITAL',
    honorDecorative : false
  });

  // 2) Full SEO
  installSiteBootstrap({
    relaxedDynamic : true,
    autoRSS        : true
  });

  // 3) SD-only bridge
  installSeoBridge({ relaxedDynamic: true });

  // 4) Tiny ops log
  runOpsLite().catch(function(){});

  // 5) Submit Request — auto-fill order ID
  var path = (wixLocationFrontend.path || []).join('/').toLowerCase();
  if (path === 'submitrequest' || path === 'submit-request') {
    fillSubmitRequestForm();
  }
});

function fillSubmitRequestForm() {
  console.log('[SR] fillSubmitRequestForm running');

  // Fetch all orders for logged-in member
  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) { console.log('[SR] No member'); return null; }
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      if (!email) { console.log('[SR] No email'); return null; }
      console.log('[SR] Email:', email);
      return getMyOrderIdList(email);
    })
    .then(function (orderIds) {
      if (!orderIds || orderIds.length === 0) {
        console.log('[SR] No orders found');
        return;
      }
      console.log('[SR] Orders:', orderIds.length);

      // Populate dropdown with all order IDs
      var dropdownOptions = orderIds.map(function (o) {
        return { label: o.label, value: o.value };
      });

      try {
        $w('#dropdown_sr').options = dropdownOptions;
        console.log('[SR] Dropdown populated:', dropdownOptions.length);
      } catch (e) { console.error('[SR] Dropdown populate failed:', e); }

      // Check URL param — pre-select that order
      var query = wixLocationFrontend.query || {};
      var urlOrderId = query.orderId || '';
      var selectedId = urlOrderId || orderIds[0].value;

      // Set dropdown selection
      try {
        $w('#dropdown_sr').value = selectedId;
        console.log('[SR] Dropdown selected:', selectedId);
      } catch (e) { console.error('[SR] Dropdown select failed:', e); }

      // Set form field to selected order
      try {
        $w('#form1').setFieldValues({ order_id_1: selectedId });
        console.log('[SR] Form set:', selectedId);
      } catch (e) { console.error('[SR] Form set failed:', e); }

      // Wire dropdown change → update form field
      try {
        $w('#dropdown_sr').onChange(function (event) {
          var val = event.target.value;
          console.log('[SR] Dropdown changed:', val);
          try {
            $w('#form1').setFieldValues({ order_id_1: val });
          } catch (e2) { console.error('[SR] Form update failed:', e2); }
        });
      } catch (e) { console.error('[SR] onChange wire failed:', e); }
    })
    .catch(function (err) {
      console.error('[SR] Error:', err);
    });
}
