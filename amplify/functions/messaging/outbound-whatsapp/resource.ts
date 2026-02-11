import { defineFunction } from '@aws-amplify/backend';

export const outboundWhatsapp = defineFunction({
  name: 'wecare-outbound-whatsapp',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'base-wecare-digital-WhatsAppOutboundTable',
    MEDIA_FILES_TABLE: 'base-wecare-digital-MediaFilesTable',
    RATE_LIMIT_TABLE: 'base-wecare-digital-RateLimitTable',
    WHATSAPP_PHONE_NUMBER_ID_1: 'phone-number-id-5e020cecd221429996f6ae721cc42206',
    WHATSAPP_PHONE_NUMBER_ID_2: 'phone-number-id-abdd81f7bec24ec085a25ab9df6a6f7c',
    MEDIA_BUCKET: 'app.wecare.digital',
    S3_BUCKET: 'app.wecare.digital',
    MEDIA_OUTBOUND_PREFIX: 'whatsapp-media/whatsapp-media-outgoing/',
  },
});
