import { defineFunction } from '@aws-amplify/backend';

export const inboundWhatsappHandler = defineFunction({
  name: 'wecare-inbound-whatsapp',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'base-wecare-digital-WhatsAppInboundTable',
    MEDIA_BUCKET: 'auth.wecare.digital',
    MEDIA_INBOUND_PREFIX: 'whatsapp-media/whatsapp-media-incoming/',
    SNS_TOPIC_ARN: 'arn:aws:sns:us-east-1:775261844268:base-wecare-digital',
    OUTBOUND_WHATSAPP_FUNCTION: 'wecare-outbound-whatsapp',
    WHATSAPP_PHONE_NUMBER_ID_1: 'phone-number-id-5e020cecd221429996f6ae721cc42206',
  },
});
