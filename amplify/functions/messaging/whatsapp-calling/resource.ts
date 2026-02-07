/**
 * WhatsApp Calling Webhook Lambda
 * 
 * Deployed separately from Amplify Gen 2 (see scripts/deploy-whatsapp-calling.ps1)
 * Lambda: wecare-whatsapp-calling
 * Runtime: Python 3.12
 * Region: us-east-1
 * 
 * API Gateway Routes (k4vqzmi07b):
 *   GET    /whatsapp-calling       - Webhook verification (hub.challenge)
 *   POST   /whatsapp-calling       - Call events (connect, terminate, permission)
 *   GET    /whatsapp-calling/logs  - List call event logs
 *   DELETE /whatsapp-calling       - Clear call logs
 * 
 * Environment Variables:
 *   VERIFY_TOKEN: wecare_calling_verify_2026
 *   CALL_LOG_TABLE: base-wecare-digital-WhatsAppCallingTable
 * 
 * DynamoDB Table:
 *   base-wecare-digital-WhatsAppCallingTable (partition key: id)
 * 
 * Meta Webhook Config:
 *   Callback URL: https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-calling
 *   Verify Token: wecare_calling_verify_2026
 *   Subscribed Fields: calls
 */

export const whatsappCallingLambdaName = 'wecare-whatsapp-calling';
export const whatsappCallingTableName = 'base-wecare-digital-WhatsAppCallingTable';
