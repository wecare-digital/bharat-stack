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

function findForm() {
  var formIds = ['#form1', '#wixForms1', '#wixForms2', '#submitRequestForm'];
  for (var i = 0; i < formIds.length; i++) {
    try {
      var f = $w(formIds[i]);
      if (f && typeof f.setFieldValues === 'function') {
        console.log('[SR] Form found:', formIds[i]);
        return f;
      }
    } catch (e) {}
  }
  console.warn('[SR] No form element found');
  return null;
}

function findDropdown() {
  var ddIds = ['#dropdown_sr', '#dropdownSr', '#dropdown1', '#dropdown2'];
  for (var i = 0; i < ddIds.length; i++) {
    try {
      var el = $w(ddIds[i]);
      if (el && el.options !== undefined) {
        console.log('[SR] Dropdown found:', ddIds[i]);
        return el;
      }
    } catch (e) {}
  }
  console.warn('[SR] No dropdown element found');
  return null;
}

function setFormField(form, key, value) {
  if (!form) return;
  try {
    var fields = {};
    fields[key] = value;
    form.setFieldValues(fields);
  } catch (e) { console.error('[SR] setFieldValues failed for', key, ':', e); }
}

function fillSubmitRequestForm() {
  console.log('[SR] fillSubmitRequestForm running');

  var form = findForm();
  var dropdown = findDropdown();

  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) { console.log('[SR] Not logged in'); return null; }
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
        console.log('[SR] No orders');
        if (dropdown) try { dropdown.disable(); } catch (e) {}
        return;
      }
      console.log('[SR] Orders:', orderIds.length);

      var opts = orderIds.map(function (o) {
        return { label: o.label, value: o.value };
      });

      // URL param pre-selection or default to latest
      var query = wixLocationFrontend.query || {};
      var urlOrderId = query.orderId || '';
      var selectedId = urlOrderId || orderIds[0].value;

      // 1) Populate standalone dropdown with ALL order IDs
      if (dropdown) {
        try {
          dropdown.options = opts;
          dropdown.value = selectedId;
          console.log('[SR] Dropdown: ' + opts.length + ' options, selected: ' + selectedId);
        } catch (e) { console.error('[SR] Dropdown populate error:', e); }

        // When user picks a different order → push into form field
        try {
          dropdown.onChange(function (event) {
            var picked = event.target.value;
            console.log('[SR] Picked:', picked);
            setFormField(form, 'order_id_1', picked);
          });
        } catch (e) { console.error('[SR] onChange error:', e); }
      }

      // 2) Set the form text field (order_id_1) to selected order
      setFormField(form, 'order_id_1', selectedId);
      console.log('[SR] Done, selected:', selectedId);
    })
    .catch(function (err) {
      console.error('[SR] Error:', err);
    });
}
