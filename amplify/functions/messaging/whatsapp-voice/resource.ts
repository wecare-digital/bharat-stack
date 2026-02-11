/**
 * WhatsApp Voice Lambda - TTS via Polly + WhatsApp Audio Messages
 * 
 * Deployed separately from Amplify Gen 2 (see scripts/deploy-whatsapp-voice.ps1)
 * Lambda: wecare-whatsapp-voice
 * Runtime: Python 3.12
 * Region: us-east-1
 * 
 * API Gateway Routes (api.wecare.digital):
 *   POST   /whatsapp-voice/tts        - Generate TTS and send as WhatsApp audio
 *   POST   /whatsapp-voice/send       - Send existing audio as WhatsApp message
 *   GET    /whatsapp-voice/voices     - List available Polly voices
 *   GET    /whatsapp-voice/logs       - List sent voice messages
 *   DELETE /whatsapp-voice/clear-logs - Clear all logs
 * 
 * Environment Variables:
 *   CONTACTS_TABLE: base-wecare-digital-ContactsTable
 *   MESSAGES_TABLE: base-wecare-digital-WhatsAppOutboundTable
 *   VOICE_LOG_TABLE: base-wecare-digital-WhatsAppVoiceTable
 *   MEDIA_BUCKET: app.wecare.digital
 *   WHATSAPP_PHONE_NUMBER_ID_1: phone-number-id-5e020cecd221429996f6ae721cc42206
 *   WHATSAPP_PHONE_NUMBER_ID_2: phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c
 * 
 * IAM Permissions needed:
 *   - polly:SynthesizeSpeech
 *   - s3:PutObject, s3:GetObject on app.wecare.digital/whatsapp-media/*
 *   - socialmessaging:SendWhatsAppMessage
 *   - socialmessaging:PostWhatsAppMessageMedia
 *   - dynamodb:PutItem, Scan, DeleteItem, GetItem, BatchWriteItem
 */

export const whatsappVoiceLambdaName = 'wecare-whatsapp-voice';
export const whatsappVoiceTableName = 'base-wecare-digital-WhatsAppVoiceTable';
