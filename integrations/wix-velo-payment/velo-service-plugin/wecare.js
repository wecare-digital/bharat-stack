// Paste into the Wix-generated wecare.js payment-provider file.
import { runtime } from 'backend/wecare/runtime';
import { safeFailure } from 'backend/wecare/core';
async function invoke(method, options) {
  try { return await (await runtime()).adapter[method](options); }
  catch { return safeFailure(); }
}
export const connectAccount = options => invoke('connectAccount', options);
export const createTransaction = options => invoke('createTransaction', options);
export const refundTransaction = options => invoke('refundTransaction', options);
