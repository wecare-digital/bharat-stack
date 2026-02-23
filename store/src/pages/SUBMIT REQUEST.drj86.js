/**
 * SUBMIT REQUEST Page (drj86) — WECARE.DIGITAL
 * Same logic as a8s2j — fallback page code.
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
  console.log('[SR-drj] onReady');

  try {
    var member = await currentMember.getMember({ fieldsets: ['FULL'] });
    if (!member) { showNoOrders(); return; }

    var email = member.loginEmail || '';
    if (!email && member.contactDetails && member.contactDetails.emails) {
      email = member.contactDetails.emails[0] || '';
    }
    if (!email) { showNoOrders(); return; }

    var orderIds = await getMyOrderIdList(email);
    if (!orderIds || orderIds.length === 0) { showNoOrders(); return; }

    var options = orderIds.map(function (o) {
      return { label: o.label, value: o.value };
    });

    $w('#dropdown_sr').options = options;

    var query = wixLocationFrontend.query || {};
    var selectedId = query.orderId || options[0].value;
    $w('#dropdown_sr').value = selectedId;

    var form = getForm();
    if (form) form.setFieldValues({ order_id_1: selectedId });

  } catch (err) {
    console.error('[SR-drj]', err);
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
  if (form) { try { form.setFieldValues({ order_id_1: '' }); } catch (e) {} }
}

export function dropdown_sr_change(event) {
  var val = event.target.value;
  console.log('[SR-drj] Changed:', val);
  var form = getForm();
  if (form) form.setFieldValues({ order_id_1: val });
}
