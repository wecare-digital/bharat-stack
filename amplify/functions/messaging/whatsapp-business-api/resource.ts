import { defineFunction } from '@aws-amplify/backend';

export const whatsappBusinessApi = defineFunction({
  name: 'wecare-whatsapp-business-api',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    META_API_VERSION: 'v20.0',
    META_TOKEN_SECRET: 'wecare/meta-system-user-token',
    WIX_ORDERS_CACHE_TABLE: 'base-wecare-digital-WixOrdersCache',
    WIX_ORDER_IDS_TABLE: 'base-wecare-digital-WixOrderIds',
    FLOW_PRIVATE_KEY_SECRET: 'wecare/flow-private-key',
    FLOW_PRIVATE_KEY_PASSPHRASE: '',
    WIX_SITE_URL: 'https://www.wecare.digital',
  },
});
