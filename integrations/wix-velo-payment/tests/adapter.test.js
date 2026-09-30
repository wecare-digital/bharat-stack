import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { createAdapter, paise, eventFromVerifiedRecord } from '../backend/wecare/core.js';
import { verifyNotification } from '../backend/wecare/security.js';
const config = { initiationEnabled: true, merchantId: 'merchant-1', accountId: 'wecare-1',
  hostedOrigins: ['https://pay.example.test'], returnOrigins: ['https://cashier.example.test'] };
const options = () => ({ wixMerchantId: config.merchantId, merchantCredentials: { accountId: config.accountId },
  wixTransactionId: 'wix-tx-1', order: { _id: 'wix-order-1', description: { currency: 'INR', totalAmount: '10001' },
    returnUrls: Object.fromEntries(['successUrl','errorUrl','cancelUrl','pendingUrl']
      .map(key => [key, `https://cashier.example.test/${key}`])) } });
const good = { ready: true, wixTransactionId: 'wix-tx-1', wixOrderId: 'wix-order-1',
  accountId: config.accountId, amountPaise: 10001, currency: 'INR',
  pluginTransactionId: 'attempt-1', redirectUrl: 'https://pay.example.test/session/opaque' };
const adapter = (bridge = async () => good) => createAdapter({ ...config, bridge });
test('hosted checkout returns only Wix response and stable retry key', async () => {
  const calls = [];
  const a = adapter(async (op, body) => { calls.push({op, body}); return good; });
  const first = await a.createTransaction(options());
  assert.deepEqual(first, { pluginTransactionId: 'attempt-1', redirectUrl: good.redirectUrl });
  await a.createTransaction(options());
  assert.equal(calls[0].body.idempotencyKey, calls[1].body.idempotencyKey);
  assert.equal(calls[0].body.amountPaise, 10001);
  assert.equal(calls[0].body.merchantCredentials, undefined);
});
for (const amount of ['0', '-1', '1.1', '1e3', '001', '9007199254740992', 1.2, null]) {
  test(`reject invalid paise ${amount}`, () => assert.throws(() => paise(amount)));
}
for (const [name, change] of [
  ['merchant', o => { o.wixMerchantId = 'other'; }],
  ['account', o => { o.merchantCredentials.accountId = 'other'; }],
  ['currency', o => { o.order.description.currency = 'USD'; }],
  ['return URL', o => { o.order.returnUrls.successUrl = 'https://evil.test'; }],
  ['missing order', o => { delete o.order._id; }]
]) test(`reject ${name} before bridge`, async () => {
  let calls = 0; const o = options(); change(o);
  const r = await adapter(async () => { calls++; return good; }).createTransaction(o);
  assert.equal(r.reasonCode, 6000); assert.equal(calls, 0);
});
for (const [name, change] of [
  ['readiness', {ready:false}], ['one paise', {amountPaise:10000}],
  ['wrong transaction', {wixTransactionId:'other'}], ['wrong order', {wixOrderId:'other'}],
  ['wrong account', {accountId:'other'}], ['redirect', {redirectUrl:'https://evil.test'}],
  ['missing redirect', {redirectUrl:undefined}]
]) test(`reject bridge ${name}`, async () => {
  const r = await adapter(async () => ({...good,...change})).createTransaction(options());
  assert.equal(r.reasonCode,6000); assert.equal(r.pluginTransactionId,undefined);
});
test('network errors do not leak credentials or imply approval', async () => {
  const r = await adapter(async () => { throw new Error('secret-token'); }).createTransaction(options());
  assert.equal(r.reasonCode,6000); assert.ok(!JSON.stringify(r).includes('secret-token'));
});
test('connect requires backend confirmation and verified account binding', async () => {
  const o = {wixMerchantId:config.merchantId,credentials:{accountId:config.accountId},currency:'INR',country:'IN'};
  const a = adapter(async () => ({connected:true,accountId:config.accountId}));
  assert.equal((await a.connectAccount(o)).accountId, config.accountId);
  assert.equal((await adapter().connectAccount(o)).reasonCode,6000);
});
test('refund accepted is not refund completed; uses independent refund key', async () => {
  const o = {merchantCredentials:{accountId:config.accountId},wixTransactionId:'tx',
    pluginTransactionId:'attempt',wixRefundId:'refund',refundAmount:100};
  let captured;
  const response = {wixTransactionId:'tx',pluginTransactionId:'attempt',wixRefundId:'refund',
    accountId:config.accountId,amountPaise:100,pluginRefundId:'rzp-refund',status:'PENDING'};
  const a = adapter(async (_, body) => { captured = body; return response; });
  assert.equal((await a.refundTransaction(o)).reasonCode,6000);
  assert.equal(captured.idempotencyKey, 'refund:merchant-1:refund');
  response.status='REFUNDED_VERIFIED';
  assert.deepEqual(await a.refundTransaction(o), {pluginRefundId:'rzp-refund'});
});
const record = {verified:true,accountId:config.accountId,wixMerchantId:config.merchantId,
  currency:'INR',amountPaise:10001,kind:'transaction',status:'PAID_VERIFIED',
  wixTransactionId:'tx',pluginTransactionId:'attempt'};
test('only verified terminal states produce Wix events', () => {
  assert.deepEqual(eventFromVerifiedRecord(record,config),{event:{transaction:{wixTransactionId:'tx',pluginTransactionId:'attempt'}}});
  for (const change of [{verified:false},{status:'PENDING'},{accountId:'other'},{currency:'USD'},{status:'CAPTURED'}])
    assert.throws(() => eventFromVerifiedRecord({...record,...change},config));
  assert.equal(eventFromVerifiedRecord({...record,status:'CANCELLED'},config).event.transaction.reasonCode,3030);
});
test('verified refund maps paise to Wix amount string', () => {
  const event = eventFromVerifiedRecord({...record,kind:'refund',status:'REFUNDED_VERIFIED',
    wixRefundId:'refund',pluginRefundId:'rzp-refund'},config);
  assert.equal(event.event.refund.amount,'10001');
});
test('callback signature binds timestamp and exact raw bytes', () => {
  const body='{"eventId":"evt-1"}', timestamp='1790769600', key='x'.repeat(32);
  const signature=createHmac('sha256',key).update(`${timestamp}.${body}`).digest('hex');
  const headers={'x-wecare-timestamp':timestamp,'x-wecare-signature':signature};
  verifyNotification(body,headers,key,Number(timestamp)*1000);
  assert.throws(() => verifyNotification(body+' ',headers,key,Number(timestamp)*1000));
  assert.throws(() => verifyNotification(body,headers,key,Number(timestamp)*1000+300001));
  assert.throws(() => verifyNotification(body,{...headers,'x-wecare-signature':'0'.repeat(64)},key,Number(timestamp)*1000));
});

test('initiation is disabled unless explicitly enabled', async () => {
  let calls=0;
  const a=createAdapter({...config,initiationEnabled:false,bridge:async () => {calls++;return good;}});
  assert.equal((await a.createTransaction(options())).reasonCode,6000);
  assert.equal(calls,0);
  const {initiationEnabled,...withoutFlag}=config;
  const b=createAdapter({...withoutFlag,bridge:async () => {calls++;return good;}});
  assert.equal((await b.createTransaction(options())).reasonCode,6000);
  assert.equal(calls,0);
});
