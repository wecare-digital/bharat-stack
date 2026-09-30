import { secrets } from 'wix-secrets-backend.v2';
import { elevate } from 'wix-auth';
import { fetch } from 'wix-fetch';
import { createAdapter, httpsUrl, identifier, requireValue } from './core.js';
const readSecret = elevate(secrets.getSecretValue);

export async function runtime() {
  const result = await readSecret('WECARE_WIX_BRIDGE_CONFIG');
  // Wix documentation examples and SDK response representations differ.
  const serialized = typeof result === 'string' ? result : result?.value;
  requireValue(typeof serialized === 'string');
  const config = JSON.parse(serialized);
  identifier(config.merchantId);
  identifier(config.accountId);
  requireValue(typeof config.bridgeToken === 'string' && config.bridgeToken.length >= 32);
  requireValue(typeof config.callbackKey === 'string' && config.callbackKey.length >= 32);
  requireValue(config.callbackKey !== config.bridgeToken);
  httpsUrl(config.bridgeBaseUrl);
  requireValue(!new URL(config.bridgeBaseUrl).search && !config.bridgeBaseUrl.endsWith('/'));
  for (const name of ['hostedOrigins', 'returnOrigins']) {
    requireValue(Array.isArray(config[name]) && config[name].length > 0);
    for (const origin of config[name]) {
      httpsUrl(origin);
      requireValue(new URL(origin).origin === origin);
    }
  }
  async function bridge(operation, payload) {
    requireValue(['connect', 'create-transaction', 'refund-transaction',
      'claim-notification', 'ack-notification'].includes(operation));
    let timer;
    try {
      return await Promise.race([
        (async () => {
          const response = await fetch(`${config.bridgeBaseUrl}/${operation}`, {
            method: 'post', headers: {
              'Content-Type': 'application/json', Authorization: `Bearer ${config.bridgeToken}`
            }, body: JSON.stringify(payload)
          });
          requireValue(response.ok);
          const value = await response.json();
          requireValue(value && typeof value === 'object' && !Array.isArray(value));
          return value;
        })(),
        new Promise((_, reject) => {
          timer = setTimeout(() => reject(new Error('WECARE_BRIDGE_TIMEOUT')), 8000);
        })
      ]);
    } finally { clearTimeout(timer); }
  }
  return { config, bridge, adapter: createAdapter({ ...config, bridge }) };
}
