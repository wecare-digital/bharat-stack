/**
 * WhatsApp Business API Lambda
 *
 * API Gateway Routes (api.wecare.digital/wa-business):
 *   GET/POST /profile           - Business profile
 *   GET/POST/PUT/DELETE /flows   - WhatsApp Flows management
 *   GET/POST/DELETE /webhooks    - Webhook subscriptions
 *   GET/POST/PUT/DELETE /groups  - WhatsApp Groups
 *   POST /interactive-list       - Send interactive list messages
 *   GET/POST /calling-settings   - Calling configuration
 *   GET/POST /phone-settings     - Phone number settings
 *   GET    /username             - Get current business username
 *   GET    /username/suggestions - Get reserved username suggestions
 *   POST   /username             - Claim a username
 *   DELETE /username             - Delete current username
 *   GET    /block-users          - List blocked users
 *   POST   /block-users          - Block users (by phone or BSUID)
 *   POST   /unblock-users        - Unblock users (by phone or BSUID)
 *   GET    /payment-config       - Payment configuration
 *   POST   /flow-data            - WhatsApp Flow data endpoint
 *   GET    /submit-requests      - List submit requests
 *   GET    /flow-logs            - List flow event logs
 */
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
    META_API_VERSION: 'v25.0',
    META_TOKEN_SECRET: 'wecare/meta-system-user-token',
    WIX_ORDERS_CACHE_TABLE: 'stack-wecare-digital-WixOrdersCache',
    WIX_ORDER_IDS_TABLE: 'stack-wecare-digital-WixOrderIds',
    FLOW_PRIVATE_KEY_SECRET: 'wecare/flow-private-key',
    FLOW_PRIVATE_KEY_PASSPHRASE: '',
    WIX_SITE_URL: 'https://www.wecare.digital',
    SUBMIT_REQUESTS_TABLE: 'stack-wecare-digital-SubmitRequestsTable',
  },
});
