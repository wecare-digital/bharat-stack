/**
 * SUBMIT REQUEST Page (a8s2j) — WECARE.DIGITAL
 * Fallback: same logic as masterPage.js
 * NOTE: Wix may not pull this (one-way sync), masterPage.js is primary.
 */
import wixLocationFrontend from 'wix-location-frontend';
import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(function () {
  console.log('[SR-a8s] Page code running');
  fillForm();
});

function fillForm() {
  var dropdown = null;
  var ids = ['#dropdown_sr', '#dropdownSr', '#dropdown1', '#dropdown2'];
  for (var i = 0; i < ids.length; i++) {
    try {
      var el = $w(ids[i]);
      if (el && el.options !== undefined) { dropdown = el; console.log('[SR-a8s] Dropdown:', ids[i]); break; }
    } catch (e) {}
  }

  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) return null;
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      if (!email) return null;
      return getMyOrderIdList(email);
    })
    .then(function (orderIds) {
      if (!orderIds || orderIds.length === 0) return;
      var opts = orderIds.map(function (o) { return { label: o.label, value: o.value }; });
      var query = wixLocationFrontend.query || {};
      var selectedId = query.orderId || orderIds[0].value;

      if (dropdown) {
        try { dropdown.options = opts; dropdown.value = selectedId; } catch (e) {}
        try {
          dropdown.onChange(function (ev) {
            try { $w('#form1').setFieldValues({ order_id_1: ev.target.value }); } catch (e2) {}
          });
        } catch (e) {}
      }
      try { $w('#form1').setFieldValues({ order_id_1: selectedId }); } catch (e) {}
      try { $w('#form1').setFieldValues({ dropdown_sr: selectedId }); } catch (e) {}
    })
    .catch(function (err) { console.error('[SR-a8s] Error:', err); });
}
