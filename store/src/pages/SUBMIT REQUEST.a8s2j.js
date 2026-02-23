/**
 * SUBMIT REQUEST Page (a8s2j) — WECARE.DIGITAL
 *
 * Populates #dropdown_sr with all WD-ORD IDs for the logged-in member.
 * Syncs selection to Wix Forms V2 field key "order_id_1" via setFieldValues.
 * Default: most recent order pre-selected.
 * Fallback: "No orders found" if member has no orders.
 *
 * Elements:
 *   #dropdown_sr  — standalone Dropdown (element ID from Properties panel)
 *   #wixForms1    — Wix Forms V2 element (try #form1 as fallback)
 *   order_id_1    — Form field key (from Form Settings > Advanced)
 */

import wixLocationFrontend from 'wix-location-frontend';
import { currentMember } from 'wix-members-frontend';
import { getMyOrderIdList } from 'backend/member-orders.web.js';

var _form = null;

function getForm() {
  if (_form) return _form;
  var ids = ['#wixForms1', '#form1', '#wixForms2', '#submitRequestForm'];
  for (var i = 0; i < ids.length; i++) {
    try {
      var f = $w(ids[i]);
      if (f && typeof f.setFieldValues === 'function') {
        _form = f;
        console.log('[SR] Form:', ids[i]);
        return f;
      }
    } catch (e) {}
  }
  return null;
}

$w.onReady(async function () {
  console.log('[SR-a8s] onReady');

  try {
    var member = await currentMember.getMember({ fieldsets: ['FULL'] });
    if (!member) {
      console.log('[SR-a8s] Not logged in');
      showNoOrders();
      return;
    }

    var email = member.loginEmail || '';
    if (!email && member.contactDetails && member.contactDetails.emails) {
      email = member.contactDetails.emails[0] || '';
    }
    if (!email) {
      console.log('[SR-a8s] No email');
      showNoOrders();
      return;
    }

    console.log('[SR-a8s] Email:', email);
    var orderIds = await getMyOrderIdList(email);

    if (!orderIds || orderIds.length === 0) {
      console.log('[SR-a8s] No orders');
      showNoOrders();
      return;
    }

    // Map to dropdown options
    var options = orderIds.map(function (o) {
      return { label: o.label, value: o.value };
    });

    // Populate dropdown
    $w('#dropdown_sr').options = options;

    // Check URL param for pre-selection, else latest
    var query = wixLocationFrontend.query || {};
    var urlOrderId = query.orderId || '';
    var selectedId = urlOrderId || options[0].value;

    $w('#dropdown_sr').value = selectedId;
    console.log('[SR-a8s] Dropdown:', options.length, 'opts, selected:', selectedId);

    // Sync to form
    var form = getForm();
    if (form) {
      form.setFieldValues({ order_id_1: selectedId });
      console.log('[SR-a8s] Form set:', selectedId);
    }

  } catch (err) {
    console.error('[SR-a8s] Error:', err);
    showNoOrders();
  }
});

function showNoOrders() {
  try {
    $w('#dropdown_sr').options = [{ label: 'No orders found', value: '' }];
    $w('#dropdown_sr').value = '';
    $w('#dropdown_sr').placeholder = 'No orders found';
  } catch (e) {}
  var form = getForm();
  if (form) {
    try { form.setFieldValues({ order_id_1: '' }); } catch (e) {}
  }
}

// Wix event handler — connect in Properties & Events panel
export function dropdown_sr_change(event) {
  var val = event.target.value;
  console.log('[SR-a8s] Changed:', val);
  var form = getForm();
  if (form) {
    form.setFieldValues({ order_id_1: val });
  }
}
