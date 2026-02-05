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
    WHATSAPP_PHONE_NUMBER_ID_1: 'phone-number-id-2ff05755631b41f29151c0573b7a4e2a',
    WHATSAPP_PHONE_NUMBER_ID_2: 'phone-number-id-66d2d11e0aea4f14a3a0df30ec5e3bc6',
    MEDIA_BUCKET: 'auth.wecare.digital',
    MEDIA_OUTBOUND_PREFIX: 'whatsapp-media/whatsapp-media-outgoing/',
  },
});
