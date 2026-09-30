import { createHmac, timingSafeEqual } from 'crypto';
import { requireValue } from './core.js';
export function verifyNotification(rawBody, headers, key, now = Date.now()) {
  requireValue(typeof rawBody === 'string' && Buffer.byteLength(rawBody, 'utf8') <= 8192);
  const timestamp = headers['x-wecare-timestamp'];
  const signature = headers['x-wecare-signature'];
  requireValue(typeof timestamp === 'string' && /^[0-9]{10}$/.test(timestamp));
  requireValue(Math.abs(now - Number(timestamp) * 1000) <= 300000);
  requireValue(typeof key === 'string' && key.length >= 32);
  requireValue(typeof signature === 'string' && /^[a-f0-9]{64}$/.test(signature));
  const expected = createHmac('sha256', key).update(`${timestamp}.${rawBody}`).digest();
  requireValue(timingSafeEqual(expected, Buffer.from(signature, 'hex')));
}
