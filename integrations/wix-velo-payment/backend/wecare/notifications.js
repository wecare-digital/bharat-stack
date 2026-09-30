import { identifier, requireValue, eventFromVerifiedRecord } from './core.js';
import { verifyNotification } from './security.js';

// Testable HTTP orchestration. Durable leases and authoritative records stay in AWS.
export function notificationHandler({ loadRuntime, submitEvent, now = Date.now }) {
  return async request => {
    let context;
    try { context = await loadRuntime(); } catch { return 503; }
    let eventId;
    try {
      const body = await request.body.text();
      const headers = Object.fromEntries(Object.entries(request.headers)
        .map(([key, value]) => [key.toLowerCase(), value]));
      verifyNotification(body, headers, context.config.callbackKey, now());
      const notification = JSON.parse(body);
      requireValue(notification && typeof notification === 'object' &&
        !Array.isArray(notification) && Object.keys(notification).length === 1);
      eventId = identifier(notification.eventId);
    } catch { return 401; }
    try {
      const scope = { eventId, wixMerchantId: context.config.merchantId,
        accountId: context.config.accountId };
      const claim = await context.bridge('claim-notification', scope);
      requireValue(claim.eventId === eventId);
      if (claim.state === 'ACKED') return 200;
      requireValue(claim.state === 'CLAIMED');
      const leaseToken = identifier(claim.leaseToken);
      const event = eventFromVerifiedRecord(claim.record, context.config);
      await submitEvent(event);
      const ack = await context.bridge('ack-notification', { ...scope, leaseToken });
      requireValue(ack.state === 'ACKED' && ack.eventId === eventId);
      return 200;
    } catch { return 503; }
  };
}
