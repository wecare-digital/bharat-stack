/**
 * Convenience Fee — WECARE.DIGITAL Checkout
 *
 * Wix eCommerce Additional Fees Service Plugin (SPI).
 * Must be in backend/ecom/additional-fees/ to be auto-discovered by Wix.
 *
 * Adds a convenience fee at checkout:
 *   Base fee: 2% of cart subtotal
 *   GST on fee: 18%
 *   Total fee: subtotal × 0.02 × 1.18
 *
 * The SPI entry point is calculateAdditionalFees() — Wix calls this
 * automatically during checkout to get any extra fees to add.
 *
 * Docs: https://dev.wix.com/docs/velo/api-reference/wix-ecom/service-plugins/additional-fees
 */

const FEE_RATE = 0.02;     // 2%
const GST_RATE = 0.18;     // 18% GST on the fee itself
const FEE_NAME = 'Convenience Fee';
const MIN_SUBTOTAL = 0;    // Apply to all orders (set > 0 to add threshold)

/**
 * Calculate convenience fee breakdown for a given subtotal.
 * @param {number} subtotal - Cart subtotal in base currency (INR)
 * @returns {{ fee: number, gst: number, total: number, label: string }}
 */
export function calculateConvenienceFee(subtotal) {
  if (!subtotal || subtotal <= MIN_SUBTOTAL) {
    return { fee: 0, gst: 0, total: 0, label: FEE_NAME };
  }

  const baseFee = Math.round(subtotal * FEE_RATE * 100) / 100;
  const gst = Math.round(baseFee * GST_RATE * 100) / 100;
  const total = Math.round((baseFee + gst) * 100) / 100;

  return {
    fee: baseFee,
    gst,
    total,
    label: `${FEE_NAME} (2% + 18% GST)`,
  };
}

/**
 * Wix eCommerce Additional Fees SPI entry point.
 * Called automatically by Wix during checkout.
 *
 * @param {object} options - { lineItems, shippingAddress, buyerDetails, ... }
 * @returns {{ additionalFees: Array<{ code, name, price, taxDetails }> }}
 */
export function calculateAdditionalFees(options) {
  const { lineItems = [] } = options;

  // Calculate subtotal from line items
  const subtotal = lineItems.reduce((sum, item) => {
    const price = parseFloat(
      item.price?.amount
      || item.fullPrice?.amount
      || item.priceBeforeDiscounts?.amount
      || '0'
    );
    const qty = parseInt(item.quantity, 10) || 1;
    return sum + (price * qty);
  }, 0);

  const { total, label } = calculateConvenienceFee(subtotal);

  if (total <= 0) {
    return { additionalFees: [] };
  }

  return {
    additionalFees: [
      {
        code: 'convenience-fee',
        name: label,
        price: {
          amount: total.toFixed(2),
          currency: 'INR',
        },
        taxDetails: {
          taxable: false, // GST is already included in the fee amount
        },
      },
    ],
  };
}

// Keep the old export name as alias for backward compatibility
export const getAdditionalFees = calculateAdditionalFees;
