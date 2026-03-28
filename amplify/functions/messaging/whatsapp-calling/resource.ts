/**
 * WhatsApp Unified Webhook + Call Control Lambda
 * 
 * Deployed separately from Amplify Gen 2 (see scripts/deploy-whatsapp-calling.ps1)
 * Lambda: wecare-whatsapp-calling
 * Runtime: Python 3.12
 * Region: us-east-1
 * 
 * UNIFIED ENDPOINT: https://api.wecare.digital/whatsapp
 * Handles BOTH messaging webhooks AND calling webhooks.
 * The old /whatsapp-calling endpoint has been deleted.
 * 
 * API Gateway Routes (api.wecare.digital):
 *   GET    /whatsapp                  - Webhook verification (hub.challenge)
 *   POST   /whatsapp                  - Webhook events from Meta (calls + messages)
 *   GET    /whatsapp/logs             - List call event logs
 *   GET    /whatsapp/active           - Get active/ringing calls (frontend polling)
 *   GET    /whatsapp/config           - Get auto-pickup config (enabled, mode, ivrUrl)
 *   POST   /whatsapp/config           - Update auto-pickup config (toggle, mode, ivrUrl)
 *   POST   /whatsapp/accept           - Pre-accept + accept call (send SDP answer)
 *   POST   /whatsapp/reject           - Reject a ringing call
 *   POST   /whatsapp/hangup           - Hang up an active call
 *   POST   /whatsapp/outbound         - Request call permission or initiate outbound call
 *   POST   /whatsapp/ai-respond       - AI Bot: audio/text → Transcribe → Bedrock → Polly TTS → audio URL
 *   DELETE /whatsapp                  - Clear call logs
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
 *   AUTO_PICKUP_IVR_URL: https://app.wecare.digital/stream/media/ivr/ivr.mp3
 *   WHATSAPP_PHONE_NUMBER_ID_1: phone-number-id-waba3-direct-1016149501586345
 *   WHATSAPP_PHONE_NUMBER_ID_2: phone-number-id-waba-t-direct-1055232054343117
 *   INBOUND_HANDLER_FUNCTION: wecare-inbound-whatsapp (for forwarding messages)
 *   AI_AGENT_ID: Z4YAK0ZLBO (external Bedrock agent)
 *   AI_AGENT_ALIAS: WANPKHQGIB
 *   AI_KB_ID: static-faq (static knowledge base, free)
 *   AI_VOICE_ID: Kajal (Polly neural voice, en-IN)
 *   AI_LANGUAGE: en-IN
 *   TRANSCRIBE_LANGUAGE: en-IN
 * 
 * Auto-Pickup Modes (configurable via SystemConfig):
 *   manual - Connect call, human answers via browser WebRTC
 *   ivr    - Auto-answer with SDP, play IVR audio, send menu, then hang up (default)
 * 
 * IVR Audio Playback:
 *   Graph API mode: pre_accept with SDP answer → accept → send audio message → terminate
 *   SIP mode: Asterisk handles IVR audio playback via RTP/SRTP (true in-call audio)
 *   For true in-call IVR audio, enable SIP on the phone number and route through Asterisk.
 * 
 * DynamoDB Tables:
 *   stack-wecare-digital-WhatsAppCallingTable (partition key: id)
 *   stack-wecare-digital-SystemConfigTable (partition key: id)
 * 
 * Meta Webhook Config:
 *   Callback URL: https://api.wecare.digital/whatsapp
 *   Verify Token: wecare_calling_verify_2026
 *   Subscribed Fields: messages, calls, account_update, account_settings_update, ...
 */

export const whatsappCallingLambdaName = 'wecare-whatsapp-calling';
export const whatsappCallingTableName = 'stack-wecare-digital-WhatsAppCallingTable';
