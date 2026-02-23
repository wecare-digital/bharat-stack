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

  // Try to find dropdown — could be #dropdown_sr or #dropdownSr
  var dropdown = null;
  var dropdownIds = ['#dropdown_sr', '#dropdownSr', '#dropdown1', '#dropdown2'];
  for (var d = 0; d < dropdownIds.length; d++) {
    try {
      var el = $w(dropdownIds[d]);
      if (el && el.options !== undefined) {
        dropdown = el;
        console.log('[SR] Found dropdown:', dropdownIds[d]);
        break;
      }
    } catch (e) { /* not found, try next */ }
  }
  if (!dropdown) console.warn('[SR] No dropdown element found');

  // Fetch all orders for logged-in member
  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) { console.log('[SR] No member logged in'); return null; }
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      if (!email) { console.log('[SR] No email found'); return null; }
      console.log('[SR] Email:', email);
      return getMyOrderIdList(email);
    })
    .then(function (orderIds) {
      if (!orderIds || orderIds.length === 0) {
        console.log('[SR] No orders found');
        return;
      }
      console.log('[SR] Orders found:', orderIds.length);

      // Build dropdown options
      var opts = orderIds.map(function (o) {
        return { label: o.label, value: o.value };
      });

      // Check URL param for pre-selection
      var query = wixLocationFrontend.query || {};
      var urlOrderId = query.orderId || '';
      var selectedId = urlOrderId || orderIds[0].value;

      // 1) Populate standalone dropdown with ALL orders
      if (dropdown) {
        try {
          dropdown.options = opts;
          dropdown.value = selectedId;
          console.log('[SR] Dropdown set:', opts.length, 'options, selected:', selectedId);
        } catch (e) { console.error('[SR] Dropdown set failed:', e); }

        // Wire: when user picks from dropdown → update form text field
        try {
          dropdown.onChange(function (event) {
            var picked = event.target.value;
            console.log('[SR] User picked:', picked);
            try {
              $w('#form1').setFieldValues({ order_id_1: picked });
            } catch (e2) { console.error('[SR] Form update on change failed:', e2); }
          });
        } catch (e) { console.error('[SR] onChange failed:', e); }
      }

      // 2) Also set the form text field to the selected/latest order
      try {
        $w('#form1').setFieldValues({ order_id_1: selectedId });
        console.log('[SR] Form field set:', selectedId);
      } catch (e) { console.error('[SR] setFieldValues failed:', e); }

      // 3) Try setting dropdown_sr as a form field too (in case it's inside the form)
      try {
        $w('#form1').setFieldValues({ dropdown_sr: selectedId });
        console.log('[SR] Form dropdown_sr field set:', selectedId);
      } catch (e) { /* may not exist as form field */ }
    })
    .catch(function (err) {
      console.error('[SR] Error:', err);
    });
}
