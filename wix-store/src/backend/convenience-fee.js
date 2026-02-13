/**
 * backend/convenience-fee.js
 * Adds a Convenience Fee to Wix Store checkout.
 *
 * Formula (same as pay/WhatsApp):
 *   convBase = round(itemTotal * 2 / 100)
 *   convGst  = round(convBase * 18 / 100)
 *   convTotal = convBase + convGst
 *
 * Wording: "Convenience Fee (Collected by Bank)" — same as pay for WhatsApp
 *
 * Implementation: Uses Wix eCommerce Additional Fees SPI.
 * This file exports the SPI handler that Wix calls during checkout.
 *
 * Setup in Wix:
 *   1. In Wix Dashboard → Developer Tools → Service Plugins → Additional Fees
 *   2. Create a new plugin pointing to this file
 *   3. Or use the ecom/additional-fees SPI pattern
 */

const CONV_FEE_PERCENT = 2;    // 2% of item total
const CONV_GST_PERCENT = 18;   // 18% GST on the fee
const FEE_NAME = 'Convenience Fee (Collected by Bank)';
const FEE_CODE = 'CONV_FEE';

/**
 * Calculate convenience fee from item total (in currency units, e.g. rupees).
 */
function calculateConvenienceFee(itemTotal) {
  const convBase = Math.round(itemTotal * CONV_FEE_PERCENT / 100);
  const convGst = Math.round(convBase * CONV_GST_PERCENT / 100);
  const convTotal = convBase + convGst;
  return { convBase, convGst, convTotal };
}

/**
 * Wix eCommerce Additional Fees SPI handler.
 * Called automatically by Wix during checkout to calculate additional fees.
 *
 * @param {Object} options - Contains lineItems, shippingAddress, buyerDetails, etc.
 * @returns {Object} - Additional fees to add to the order
 */
export function getAdditionalFees(options) {
  const { lineItems } = options;

  // Calculate total item value from all line items
  let itemTotal = 0;
  if (lineItems && lineItems.length > 0) {
    for (const item of lineItems) {
      const price = Number(item.price) || 0;
      const quantity = Number(item.quantity) || 1;
      itemTotal += price * quantity;
    }
  }

  // Don't add fee for zero-value carts
  if (itemTotal <= 0) {
    return { additionalFees: [] };
  }

  const { convBase, convGst, convTotal } = calculateConvenienceFee(itemTotal);

  return {
    additionalFees: [
      {
        code: FEE_CODE,
        name: FEE_NAME,
        price: String(convTotal),
        taxDetails: {
          taxable: true,
          taxRate: '0', // GST is already included in convTotal
          taxAmount: String(convGst),
        },
        // Breakdown for transparency
        metadata: {
          feeBase: String(convBase),
          feeGst: String(convGst),
          feeTotal: String(convTotal),
          feePercent: String(CONV_FEE_PERCENT),
          gstPercent: String(CONV_GST_PERCENT),
          itemTotal: String(itemTotal),
        },
      },
    ],
    currency: 'INR',
  };
}

/**
 * Standalone calculator — can be imported by other Velo files or page code.
 */
export function calcConvFee(itemTotal) {
  return calculateConvenienceFee(itemTotal);
}
