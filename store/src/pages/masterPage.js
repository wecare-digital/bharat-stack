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

  // Check URL param first
  var query = wixLocationFrontend.query || {};
  var urlOrderId = query.orderId || '';

  if (urlOrderId) {
    try {
      $w('#form1').setFieldValues({ order_id_1: urlOrderId });
      console.log('[SR] Set from URL:', urlOrderId);
    } catch (e) { console.error('[SR] setFieldValues failed:', e); }
    return;
  }

  // Auto-fetch for logged-in member
  currentMember.getMember({ fieldsets: ['FULL'] })
    .then(function (member) {
      if (!member) return null;
      var email = member.loginEmail || '';
      if (!email && member.contactDetails && member.contactDetails.emails) {
        email = member.contactDetails.emails[0] || '';
      }
      if (!email) return null;
      console.log('[SR] Email:', email);
      return getMyOrderIdList(email);
    })
    .then(function (orderIds) {
      if (!orderIds || orderIds.length === 0) {
        console.log('[SR] No orders found');
        return;
      }
      console.log('[SR] Orders:', orderIds.length);
      $w('#form1').setFieldValues({ order_id_1: orderIds[0].value });
      console.log('[SR] Set order:', orderIds[0].value);
    })
    .catch(function (err) {
      console.error('[SR] Error:', err);
    });
}
