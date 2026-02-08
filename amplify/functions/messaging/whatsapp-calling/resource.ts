/**
 * WhatsApp Calling Webhook + Call Control Lambda
 * 
 * Deployed separately from Amplify Gen 2 (see scripts/deploy-whatsapp-calling.ps1)
 * Lambda: wecare-whatsapp-calling
 * Runtime: Python 3.12
 * Region: us-east-1
 * 
 * API Gateway Routes (k4vqzmi07b):
 *   GET    /whatsapp-calling          - Webhook verification (hub.challenge)
 *   POST   /whatsapp-calling          - Call events from Meta (connect, terminate, permission)
 *   GET    /whatsapp-calling/logs     - List call event logs
 *   GET    /whatsapp-calling/active   - Get active/ringing calls (frontend polling)
 *   GET    /whatsapp-calling/config   - Get auto-pickup config
 *   POST   /whatsapp-calling/config   - Update auto-pickup config
 *   POST   /whatsapp-calling/accept   - Pre-accept + accept call (send SDP answer)
 *   POST   /whatsapp-calling/reject   - Reject a ringing call
 *   POST   /whatsapp-calling/hangup   - Hang up an active call
 *   POST   /whatsapp-calling/outbound - Request call permission or initiate outbound call
 *   DELETE /whatsapp-calling          - Clear call logs
 * 
 * Environment Variables:
 *   VERIFY_TOKEN: wecare_calling_verify_2026
 *   CALL_LOG_TABLE: base-wecare-digital-WhatsAppCallingTable
 *   META_TOKEN_SECRET: wecare/meta-system-user-token
 *   META_API_VERSION: v20.0
 *   SYSTEM_CONFIG_TABLE: base-wecare-digital-SystemConfigTable
 *   MEDIA_BUCKET: auth.wecare.digital
 *   AUTO_PICKUP_AUDIO_KEY: whatsapp-media/whatsapp-calling/auto-pickup-greeting.ogg
 *   AUTO_PICKUP_ENABLED: false (default, overridden by SystemConfig)
 *   WHATSAPP_PHONE_NUMBER_ID_1: phone-number-id-2ff05755631b41f29151c0573b7a4e2a
 *   WHATSAPP_PHONE_NUMBER_ID_2: phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6
 * 
 * Auto-Pickup Feature:
 *   When enabled (via SystemConfig or env), incoming calls are automatically
 *   answered and a pre-recorded audio greeting (OGG/OPUS from S3) is sent
 *   to the caller as a WhatsApp audio message. Call auto-terminates after 15s.
 *   Upload greeting: s3://auth.wecare.digital/whatsapp-media/whatsapp-calling/auto-pickup-greeting.ogg
 * 
 * DynamoDB Tables:
 *   base-wecare-digital-WhatsAppCallingTable (partition key: id)
 *   base-wecare-digital-SystemConfigTable (partition key: configKey)
 * 
 * Meta Webhook Config:
 *   Callback URL: https://k4vqzmi07b.execute-api.us-east-1.amazonaws.com/prod/whatsapp-calling
 *   Verify Token: wecare_calling_verify_2026
 *   Subscribed Fields: calls
 */

export const whatsappCallingLambdaName = 'wecare-whatsapp-calling';
export const whatsappCallingTableName = 'base-wecare-digital-WhatsAppCallingTable';
