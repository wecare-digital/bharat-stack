import test from 'node:test';
import assert from 'node:assert/strict';
import { createHmac } from 'node:crypto';
import { notificationHandler } from '../backend/wecare/notifications.js';
const timestamp = '1790769600';
const config = {merchantId:'merchant-1',accountId:'account-1',callbackKey:'k'.repeat(32)};
const record = {verified:true,wixMerchantId:config.merchantId,accountId:config.accountId,
  currency:'INR',amountPaise:100,kind:'transaction',status:'PAID_VERIFIED',
  wixTransactionId:'tx-1',pluginTransactionId:'attempt-1'};
const signedRequest = (payload={eventId:'event-1'}, key=config.callbackKey) => {
  const body=JSON.stringify(payload);
  return {body:{text:async()=>body},headers:{'X-Wecare-Timestamp':timestamp,
    'X-Wecare-Signature':createHmac('sha256',key).update(`${timestamp}.${body}`).digest('hex')}};
};
function fixture({claim={},ack={},submitFailure=false,bridgeFailure=false}={}) {
  const calls=[];
  const handler=notificationHandler({now:()=>Number(timestamp)*1000,
    loadRuntime:async()=>({config,bridge:async(operation,payload)=>{
      calls.push({operation,payload});
      if(bridgeFailure) throw new Error('unavailable');
      return operation==='claim-notification'
        ? {eventId:'event-1',state:'CLAIMED',leaseToken:'lease-1',record,...claim}
        : {eventId:'event-1',state:'ACKED',...ack};
    }}), submitEvent:async event=>{calls.push({operation:'submitEvent',event});
      if(submitFailure) throw new Error('wix unavailable');}
  });
  return {handler,calls};
}
test('signed callback claims, submits verified event, then acknowledges lease',async()=>{
  const {handler,calls}=fixture();
  assert.equal(await handler(signedRequest()),200);
  assert.deepEqual(calls.map(x=>x.operation),['claim-notification','submitEvent','ack-notification']);
  assert.equal(calls[2].payload.leaseToken,'lease-1');
  assert.deepEqual(calls[1].event,{event:{transaction:{wixTransactionId:'tx-1',pluginTransactionId:'attempt-1'}}});
});
test('bad signature never reaches bridge or Wix',async()=>{
  const {handler,calls}=fixture();
  assert.equal(await handler(signedRequest(undefined,'bad key')),401);
  assert.equal(calls.length,0);
});
test('callback cannot inject a status even with valid signature',async()=>{
  const {handler,calls}=fixture();
  assert.equal(await handler(signedRequest({eventId:'event-1',status:'PAID_VERIFIED'})),401);
  assert.equal(calls.length,0);
});
test('already-ACKed duplicate does not submit twice',async()=>{
  const {handler,calls}=fixture({claim:{state:'ACKED'}});
  assert.equal(await handler(signedRequest()),200);
  assert.deepEqual(calls.map(x=>x.operation),['claim-notification']);
});
for(const [label,claim] of [
  ['busy lease',{state:'BUSY'}],['wrong event',{eventId:'other'}],
  ['unverified',{record:{...record,verified:false}}],['wrong account',{record:{...record,accountId:'other'}}],
  ['pending',{record:{...record,status:'PENDING'}}],['invalid lease',{leaseToken:''}]
])test(`${label} refuses Wix mutation and ACK`,async()=>{
  const {handler,calls}=fixture({claim});
  assert.equal(await handler(signedRequest()),503);
  assert.deepEqual(calls.map(x=>x.operation),['claim-notification']);
});
test('Wix failure leaves lease unacknowledged for reconciliation',async()=>{
  const {handler,calls}=fixture({submitFailure:true});
  assert.equal(await handler(signedRequest()),503);
  assert.deepEqual(calls.map(x=>x.operation),['claim-notification','submitEvent']);
});
test('lost ACK is retryable, not a claim of exactly-once completion',async()=>{
  const {handler}=fixture({ack:{state:'UNKNOWN'}});
  assert.equal(await handler(signedRequest()),503);
});
test('bridge or secret outage fails closed',async()=>{
  assert.equal(await fixture({bridgeFailure:true}).handler(signedRequest()),503);
  const handler=notificationHandler({loadRuntime:async()=>{throw new Error('secret unavailable');},
    submitEvent:async()=>assert.fail('must not submit')});
  assert.equal(await handler(signedRequest()),503);
});
test('verified refund callback uses stored refund ID and amount',async()=>{
  const {handler,calls}=fixture({claim:{record:{...record,kind:'refund',status:'REFUNDED_VERIFIED',
    wixRefundId:'wix-refund-1',pluginRefundId:'refund-1'}}});
  assert.equal(await handler(signedRequest()),200);
  assert.deepEqual(calls[1].event,{event:{refund:{wixTransactionId:'tx-1',wixRefundId:'wix-refund-1',
    pluginRefundId:'refund-1',amount:'100'}}});
});
