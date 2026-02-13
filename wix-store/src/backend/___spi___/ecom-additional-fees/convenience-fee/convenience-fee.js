/**
 * convenience-fee.js
 * Wix eCommerce Additional Fees SPI — Convenience Fee (Collected by Bank)
 *
 * Same formula as pay/WhatsApp:
 *   convBase = round(itemTotal * 2 / 100)
 *   convGst  = round(convBase * 18 / 100)
 *   convTotal = convBase + convGst
 *
 * Wording: "Convenience Fee (Collected by Bank)"
 */

const CONV_FEE_PERCENT = 2;
const CONV_GST_PERCENT = 18;

/**
 * Called by Wix eCommerce when cart totals are calculated.
 * @param {Object} options - Contains lineItems, shippingAddress, buyerDetails, etc.
 * @returns {Object} - { additionalFees: [...], currency: "INR" }
 */
export const calculateAdditionalFees = (options) => {
  console.log('[CONV-FEE] calculateAdditionalFees called');
  console.log('[CONV-FEE] options keys:', Object.keys(options || {}));
  console.log('[CONV-FEE] full options:', JSON.stringify(options, null, 2));

  const lineItems = options?.lineItems || [];
  console.log('[CONV-FEE] lineItems count:', lineItems.length);

  let itemTotal = 0;
  for (const item of lineItems) {
    console.log('[CONV-FEE] item:', JSON.stringify(item));
    const price = Number(item.price) || 0;
    const quantity = Number(item.quantity) || 1;
    itemTotal += price * quantity;
  }

  console.log('[CONV-FEE] itemTotal:', itemTotal);

  if (itemTotal <= 0) {
    console.log('[CONV-FEE] itemTotal <= 0, returning empty fees');
    return { additionalFees: [], currency: 'INR' };
  }

  const convBase = Math.round(itemTotal * CONV_FEE_PERCENT / 100);
  const convGst = Math.round(convBase * CONV_GST_PERCENT / 100);
  const convTotal = convBase + convGst;

  console.log('[CONV-FEE] convBase:', convBase, 'convGst:', convGst, 'convTotal:', convTotal);

  const result = {
    additionalFees: [
      {
        code: 'CONV_FEE',
        name: 'Convenience Fee (Collected by Bank)',
        price: String(convTotal),
        taxDetails: {
          taxable: false,
        },
      },
    ],
    currency: 'INR',
  };

  console.log('[CONV-FEE] returning:', JSON.stringify(result));
  return result;
};
