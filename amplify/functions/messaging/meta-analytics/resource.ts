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
    META_API_VERSION: 'v25.0',
    WABA1_ID: '2094615664435155',
    WABA2_ID: '2513394156072604',
    PHONE1_META_ID: '1016149501586345',
    PHONE2_META_ID: '1055232054343117',
  },
  policies: ['common', 'secrets'],
};
