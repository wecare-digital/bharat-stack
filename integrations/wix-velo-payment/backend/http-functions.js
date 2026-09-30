// Merge this export/imports into existing http-functions.js; preserve other handlers.
import { response } from 'wix-http-functions';
import wixPaymentProviderBackend from 'wix-payment-provider-backend';
import { runtime } from 'backend/wecare/runtime';
import { notificationHandler } from 'backend/wecare/notifications';
const handleNotification = notificationHandler({
  loadRuntime: runtime,
  submitEvent: event => wixPaymentProviderBackend.submitEvent(event)
});
export async function post_wecarePaymentEvent(request) {
  const status = await handleNotification(request);
  return response({ status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
    body: JSON.stringify({ ok: status === 200 })
  });
}
