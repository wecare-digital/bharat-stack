/**
 * Meta Analytics Lambda Function Resource
 * 
 * Retrieves official Meta WhatsApp analytics via Graph API.
 * Deployed separately (not managed by Amplify Gen 2).
 */
export const metaAnalytics = {
  functionName: 'wecare-meta-analytics',
  runtime: 'python3.12',
  handler: 'handler.handler',
  timeout: 30,
  memorySize: 256,
  environment: {
    META_TOKEN_SECRET: 'wecare/meta-system-user-token',
    META_API_VERSION: 'v20.0',
    WABA1_ID: '1912405516040025',
    WABA2_ID: '1633959101297902',
    PHONE1_META_ID: '960395407161423',
    PHONE2_META_ID: '997428863451102',
  },
  policies: ['common', 'secrets'],
};
