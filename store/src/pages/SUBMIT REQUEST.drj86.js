/**
 * SUBMIT REQUEST Page (drj86) — WECARE.DIGITAL
 * Fallback page code — same logic as masterPage.js
 */
import wixLocationFrontend from 'wix-location-frontend';
import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

$w.onReady(function () {
  console.log('[SR-drj] onReady');
  var form = findForm();
  var dropdown = findDropdown();

  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) return null;
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      return email ? getMyOrderIdList(email) : null;
    })
    .then(function (orderIds) {
      if (!orderIds || !orderIds.length) {
        if (dropdown) try { dropdown.disable(); } catch (e) {}
        return;
      }
      var opts = orderIds.map(function (o) { return { label: o.label, value: o.value }; });
      var query = wixLocationFrontend.query || {};
      var selectedId = query.orderId || orderIds[0].value;

      if (dropdown) {
        try { dropdown.options = opts; dropdown.value = selectedId; } catch (e) {}
        try {
          dropdown.onChange(function (ev) {
            setFormField(form, 'order_id_1', ev.target.value);
          });
        } catch (e) {}
      }
      setFormField(form, 'order_id_1', selectedId);
    })
    .catch(function (err) { console.error('[SR-drj]', err); });
});

function findForm() {
  var ids = ['#form1', '#wixForms1', '#wixForms2', '#submitRequestForm'];
  for (var i = 0; i < ids.length; i++) {
    try { var f = $w(ids[i]); if (f && typeof f.setFieldValues === 'function') return f; } catch (e) {}
  }
  return null;
}
function findDropdown() {
  var ids = ['#dropdown_sr', '#dropdownSr', '#dropdown1', '#dropdown2'];
  for (var i = 0; i < ids.length; i++) {
    try { var el = $w(ids[i]); if (el && el.options !== undefined) return el; } catch (e) {}
  }
  return null;
}
function setFormField(form, key, value) {
  if (!form) return;
  try { var f = {}; f[key] = value; form.setFieldValues(f); } catch (e) {}
}
