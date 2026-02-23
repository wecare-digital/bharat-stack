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

async function fillSubmitRequestForm() {
  console.log('[SR] fillSubmitRequestForm running');

  // Find form element (try multiple IDs)
  var form = null;
  var formIds = ['#wixForms1', '#form1', '#wixForms2', '#submitRequestForm'];
  for (var fi = 0; fi < formIds.length; fi++) {
    try {
      var f = $w(formIds[fi]);
      if (f && typeof f.setFieldValues === 'function') { form = f; console.log('[SR] Form:', formIds[fi]); break; }
    } catch (e) {}
  }

  try {
    var member = await currentMember.getMember({ fieldsets: ['FULL'] });
    if (!member) { console.log('[SR] Not logged in'); showNoOrders(form); return; }

    var email = member.loginEmail || '';
    if (!email && member.contactDetails && member.contactDetails.emails) {
      email = member.contactDetails.emails[0] || '';
    }
    if (!email) { console.log('[SR] No email'); showNoOrders(form); return; }

    console.log('[SR] Email:', email);
    var orderIds = await getMyOrderIdList(email);

    if (!orderIds || orderIds.length === 0) {
      console.log('[SR] No orders');
      showNoOrders(form);
      return;
    }

    var opts = orderIds.map(function (o) {
      return { label: o.label, value: o.value };
    });

    var query = wixLocationFrontend.query || {};
    var selectedId = query.orderId || opts[0].value;

    // Populate dropdown
    try {
      $w('#dropdown_sr').options = opts;
      $w('#dropdown_sr').value = selectedId;
      console.log('[SR] Dropdown:', opts.length, 'opts, selected:', selectedId);
    } catch (e) { console.error('[SR] Dropdown error:', e); }

    // Sync to form
    if (form) {
      try { form.setFieldValues({ order_id_1: selectedId }); console.log('[SR] Form set:', selectedId); } catch (e) {}
    }

    // Wire dropdown change → form field
    try {
      $w('#dropdown_sr').onChange(function (event) {
        var val = event.target.value;
        console.log('[SR] Picked:', val);
        if (form) { try { form.setFieldValues({ order_id_1: val }); } catch (e) {} }
      });
    } catch (e) {}

  } catch (err) {
    console.error('[SR] Error:', err);
    showNoOrders(form);
  }
}

function showNoOrders(form) {
  try {
    $w('#dropdown_sr').options = [{ label: 'No orders found', value: '' }];
    $w('#dropdown_sr').value = '';
    $w('#dropdown_sr').placeholder = 'No orders found';
  } catch (e) {}
  if (form) { try { form.setFieldValues({ order_id_1: '' }); } catch (e) {} }
}
