/**
 * WhatsApp Calling Webhook + Call Control Lambda
 * 
 * Deployed separately from Amplify Gen 2 (see scripts/deploy-whatsapp-calling.ps1)
 * Lambda: wecare-whatsapp-calling
 * Runtime: Python 3.12
 * Region: us-east-1
 * 
 * API Gateway Routes (api.wecare.digital):
 *   GET    /whatsapp-calling          - Webhook verification (hub.challenge)
 *   POST   /whatsapp-calling          - Call events from Meta (connect, terminate, permission)
 *   GET    /whatsapp-calling/logs     - List call event logs
 *   GET    /whatsapp-calling/active   - Get active/ringing calls (frontend polling)
 *   GET    /whatsapp-calling/config   - Get auto-pickup config (enabled, mode, ivrUrl)
 *   POST   /whatsapp-calling/config   - Update auto-pickup config (toggle, mode, ivrUrl)
 *   POST   /whatsapp-calling/accept   - Pre-accept + accept call (send SDP answer)
 *   POST   /whatsapp-calling/reject   - Reject a ringing call
 *   POST   /whatsapp-calling/hangup   - Hang up an active call
 *   POST   /whatsapp-calling/outbound - Request call permission or initiate outbound call
 *   POST   /whatsapp-calling/ai-respond - AI Bot: audio/text → Transcribe → Bedrock → Polly TTS → audio URL
 *   DELETE /whatsapp-calling          - Clear call logs
 * 
 * Environment Variables:
 *   VERIFY_TOKEN: wecare_calling_verify_2026
 *   CALL_LOG_TABLE: stack-wecare-digital-WhatsAppCallingTable
 *   META_TOKEN_SECRET: wecare/meta-system-user-token
 *   META_API_VERSION: v20.0
 *   SYSTEM_CONFIG_TABLE: stack-wecare-digital-SystemConfigTable
 *   MEDIA_BUCKET: app.wecare.digital
 *   AUTO_PICKUP_AUDIO_KEY: whatsapp-media/whatsapp-calling/auto-pickup-greeting.ogg
 *   AUTO_PICKUP_ENABLED: true (default ON, overridden by SystemConfig)
 *   AUTO_PICKUP_IVR_URL: https://app.wecare.digital/stream/media/ivr/IVR+1.mp3
 *   WHATSAPP_PHONE_NUMBER_ID_1: phone-number-id-5e020cecd221429996f6ae721cc42206
 *   WHATSAPP_PHONE_NUMBER_ID_2: phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
 *   INBOUND_HANDLER_FUNCTION: wecare-inbound-whatsapp (for forwarding WABA3 messages)
 *   AI_AGENT_ID: Z4YAK0ZLBO (external Bedrock agent)
 *   AI_AGENT_ALIAS: WANPKHQGIB
 *   AI_KB_ID: static-faq (static knowledge base, free)
 *   AI_VOICE_ID: Kajal (Polly neural voice, en-IN)
 *   AI_LANGUAGE: en-IN
 *   TRANSCRIBE_LANGUAGE: en-IN
 * 
 * Auto-Pickup Modes (configurable via SystemConfig):
 *   manual - Connect call, human answers via browser WebRTC
 *   ivr    - Auto-answer, play IVR audio greeting, then hang up (default)
 * 
 * DynamoDB Tables:
 *   stack-wecare-digital-WhatsAppCallingTable (partition key: id)
 *   stack-wecare-digital-SystemConfigTable (partition key: id)
 * 
 * Meta Webhook Config:
 *   Callback URL: https://api.wecare.digital/whatsapp-calling
 *   Verify Token: wecare_calling_verify_2026
 *   Subscribed Fields: calls
 */

export const whatsappCallingLambdaName = 'wecare-whatsapp-calling';
export const whatsappCallingTableName = 'stack-wecare-digital-WhatsAppCallingTable';
