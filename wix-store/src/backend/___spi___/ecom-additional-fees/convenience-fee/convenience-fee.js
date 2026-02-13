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
export function calculateAdditionalFees(options) {
  const { lineItems } = options;

  let itemTotal = 0;
  if (lineItems && lineItems.length > 0) {
    for (const item of lineItems) {
      const price = Number(item.price) || 0;
      const quantity = Number(item.quantity) || 1;
      itemTotal += price * quantity;
    }
  }

  if (itemTotal <= 0) {
    return { additionalFees: [], currency: 'INR' };
  }

  const convBase = Math.round(itemTotal * CONV_FEE_PERCENT / 100);
  const convGst = Math.round(convBase * CONV_GST_PERCENT / 100);
  const convTotal = convBase + convGst;

  return {
    additionalFees: [
      {
        code: 'CONV_FEE',
        name: 'Convenience Fee (Collected by Bank)',
        price: convTotal.toString(),
        taxDetails: {
          taxable: false,
        },
      },
    ],
    currency: 'INR',
  };
}
