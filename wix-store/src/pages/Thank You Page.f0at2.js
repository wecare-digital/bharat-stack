// Thank You page code

import { createOrGetOrderId } from 'backend/orderId';
import { currentMember } from 'wix-members-frontend';

const IST_OFFSET_MINUTES = 330;

function formatIstDateTime(isoString) {
  if (!isoString) return '';
  const d = new Date(isoString);
  if (isNaN(d.getTime())) return '';
  const istMs = d.getTime() + IST_OFFSET_MINUTES * 60 * 1000;
  const ist = new Date(istMs);

  const dd = String(ist.getUTCDate()).padStart(2, '0');
  const mm = String(ist.getUTCMonth() + 1).padStart(2, '0');
  const yyyy = ist.getUTCFullYear();
  const hh = String(ist.getUTCHours()).padStart(2, '0');
  const mi = String(ist.getUTCMinutes()).padStart(2, '0');
  const ss = String(ist.getUTCSeconds()).padStart(2, '0');

  return `${dd}-${mm}-${yyyy} ${hh}:${mi}:${ss} IST`;
}

// Build amount text from official Velo fields: order.currency + order.totals.total
function buildAmountText(order) {
  if (!order || !order.totals) return '';

  const currency = typeof order.currency === 'string'
    ? order.currency.trim()
    : '';

  const totals = order.totals || {};
  const rawTotal = totals.total;

  let base = '';

  if (typeof rawTotal === 'number' && !isNaN(rawTotal)) {
    base = rawTotal.toLocaleString('en-IN', {
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    });
  } else if (typeof rawTotal === 'string') {
    base = rawTotal.trim();
  } else if (rawTotal && typeof rawTotal === 'object') {
    if (typeof rawTotal.formattedAmount === 'string') {
      base = rawTotal.formattedAmount.trim();
    } else if (typeof rawTotal.amount === 'number' && !isNaN(rawTotal.amount)) {
      base = rawTotal.amount.toLocaleString('en-IN', {
        minimumFractionDigits: 2,
        maximumFractionDigits: 2
      });
    } else if (typeof rawTotal.amount === 'string') {
      base = rawTotal.amount.trim();
    }
  }

  if (!base) return '';

  if (currency && !base.includes(currency)) {
    return `${base} ${currency}`;
  }

  return base;
}

$w.onReady(async function () {
  $w('#orderContainer').expand();

  const thankYouWidget = $w('#thankYouPage1'); // change ID if your widget has a different ID

  let order;
  try {
    order = await thankYouWidget.getOrder(); // only works on published site
  } catch (err) {
    console.error('getOrder error:', err);
    $w('#orderIdText').text = 'Order is being processed.';
    return;
  }

  if (!order || !order._id) {
    $w('#orderIdText').text = 'Order is being processed.';
    return;
  }

  // member (checkout is members-only)
  let memberId = null;
  try {
    const member = await currentMember.getMember();
    memberId = member?._id || null;
  } catch (e) {
    console.warn('No member found at checkout');
  }

  const wixOrderId = order._id;
  const orderNumber = order.number ? String(order.number) : null;

  let buyerEmail = null;
  let buyerPhone = null;
  if (order.buyerInfo) {
    buyerEmail = order.buyerInfo.email || null;
    buyerPhone = order.buyerInfo.phone || null;
  }

  // products summary
  let productsSummary = '';
  if (Array.isArray(order.lineItems)) {
    productsSummary = order.lineItems
      .map(li => li.name)
      .filter(Boolean)
      .join(', ');
  }

  // order date
  const orderDateObj = order._createdDate || order._dateCreated || new Date();
  const orderDateIso = new Date(orderDateObj).toISOString();

  // amount text
  const amountText = buildAmountText(order);
  const currency = typeof order.currency === 'string'
    ? order.currency.trim()
    : null;

  let orderId;
  try {
    orderId = await createOrGetOrderId({
      wixOrderId,
      memberId,
      orderNumber,
      buyerEmail,
      buyerPhone,
      totalAmount: amountText,   // TEXT saved in CMS
      currency,
      productsSummary,
      orderDate: orderDateObj
    });
  } catch (err) {
    console.error('createOrGetOrderId error:', err);
    $w('#orderIdText').text = 'Order is being processed.';
    return;
  }

  // Display
  $w('#orderIdText').text = orderId;
  $w('#orderDateText').text = formatIstDateTime(orderDateIso);
  $w('#orderProductsText').text = productsSummary || '';
  $w('#orderAmountText').text = amountText || 'Amount not available';
});
