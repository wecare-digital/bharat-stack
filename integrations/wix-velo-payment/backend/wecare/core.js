// Pure adapter logic; all durable state and provider verification belong to AWS.
export function requireValue(condition) {
  if (!condition) throw new Error('WECARE_VALIDATION_FAILED');
}
export function identifier(value) {
  requireValue(typeof value === 'string' && /^[A-Za-z0-9_.:-]{1,160}$/.test(value));
  return value;
}
export function paise(value) {
  requireValue((typeof value === 'string' && /^[1-9][0-9]*$/.test(value)) ||
    (typeof value === 'number' && Number.isSafeInteger(value) && value > 0));
  const amount = Number(value);
  requireValue(Number.isSafeInteger(amount) && amount > 0);
  return amount;
}
export function httpsUrl(value, allowedOrigins) {
  const url = new URL(value);
  requireValue(url.protocol === 'https:' && !url.username && !url.password && !url.hash);
  if (allowedOrigins) requireValue(allowedOrigins.includes(url.origin));
  return value;
}
export const safeFailure = () => ({
  reasonCode: 6000,
  errorCode: 'WECARE_UNAVAILABLE',
  errorMessage: 'Unable to confirm this operation. Check its status before retrying.'
});
export function createAdapter({ bridge, merchantId, accountId, hostedOrigins, returnOrigins, initiationEnabled = false }) {
  async function safe(action) {
    try { return await action(); } catch { return safeFailure(); }
  }
  function checkMerchant(options, credentialKey) {
    requireValue(options.wixMerchantId === merchantId);
    requireValue(options[credentialKey]?.accountId === accountId);
  }
  return {
    connectAccount: options => safe(async () => {
      checkMerchant(options, 'credentials');
      requireValue(options.currency === 'INR' && options.country === 'IN');
      const result = await bridge('connect', { wixMerchantId: merchantId, accountId });
      requireValue(result.connected === true && result.accountId === accountId);
      return { credentials: { accountId }, accountId, accountName: 'WECARE.DIGITAL' };
    }),
    createTransaction: options => safe(async () => {
      requireValue(initiationEnabled === true);
      checkMerchant(options, 'merchantCredentials');
      const wixTransactionId = identifier(options.wixTransactionId);
      const wixOrderId = identifier(options.order?._id);
      const description = options.order?.description;
      requireValue(description?.currency === 'INR');
      const amountPaise = paise(description.totalAmount);
      const returnUrls = {};
      for (const key of ['successUrl', 'errorUrl', 'cancelUrl', 'pendingUrl']) {
        returnUrls[key] = httpsUrl(options.order.returnUrls?.[key], returnOrigins);
      }
      const result = await bridge('create-transaction', {
        wixMerchantId: merchantId, accountId, wixTransactionId, wixOrderId,
        amountPaise, currency: 'INR', returnUrls,
        idempotencyKey: `payment:${merchantId}:${wixTransactionId}`
      });
      // Missing readiness, account or amount evidence can never imply approval.
      requireValue(result.ready === true && result.wixTransactionId === wixTransactionId &&
        result.wixOrderId === wixOrderId && result.accountId === accountId &&
        result.amountPaise === amountPaise && result.currency === 'INR');
      return {
        pluginTransactionId: identifier(result.pluginTransactionId),
        redirectUrl: httpsUrl(result.redirectUrl, hostedOrigins)
      };
    }),
    refundTransaction: options => safe(async () => {
      // Wix's documented refund request does not include wixMerchantId.
      requireValue(options.merchantCredentials?.accountId === accountId);
      const wixTransactionId = identifier(options.wixTransactionId);
      const pluginTransactionId = identifier(options.pluginTransactionId);
      const wixRefundId = identifier(options.wixRefundId);
      const amountPaise = paise(options.refundAmount);
      const result = await bridge('refund-transaction', {
        wixMerchantId: merchantId, accountId, wixTransactionId, pluginTransactionId,
        wixRefundId, amountPaise,
        idempotencyKey: `refund:${merchantId}:${wixRefundId}`
      });
      requireValue(result.wixTransactionId === wixTransactionId &&
        result.pluginTransactionId === pluginTransactionId && result.wixRefundId === wixRefundId &&
        result.accountId === accountId && result.amountPaise === amountPaise);
      // Never report a merely accepted refund as completed.
      requireValue(result.status === 'REFUNDED_VERIFIED');
      return { pluginRefundId: identifier(result.pluginRefundId) };
    })
  };
}
export function eventFromVerifiedRecord(record, config) {
  requireValue(record?.verified === true && record.accountId === config.accountId &&
    record.wixMerchantId === config.merchantId && record.currency === 'INR');
  const base = {
    wixTransactionId: identifier(record.wixTransactionId),
    pluginTransactionId: identifier(record.pluginTransactionId)
  };
  paise(record.amountPaise);
  if (record.kind === 'transaction') {
    const reasons = { FAILED: 6000, CANCELLED: 3030, EXPIRED: 3035 };
    if (record.status === 'PAID_VERIFIED') return { event: { transaction: base } };
    requireValue(Object.hasOwn(reasons, record.status));
    return { event: { transaction: { ...base, reasonCode: reasons[record.status],
      errorCode: `WECARE_${record.status}`, errorMessage: 'Payment was not completed.' } } };
  }
  requireValue(record.kind === 'refund' && record.status === 'REFUNDED_VERIFIED');
  return { event: { refund: {
    wixTransactionId: base.wixTransactionId, wixRefundId: identifier(record.wixRefundId),
    pluginRefundId: identifier(record.pluginRefundId), amount: String(paise(record.amountPaise))
  } } };
}
