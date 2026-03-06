import { defineFunction } from '@aws-amplify/backend';

export const messagesRead = defineFunction({
  name: 'wecare-messages-read',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    INBOUND_TABLE: 'stack-wecare-digital-WhatsAppInboundTable',
    OUTBOUND_TABLE: 'stack-wecare-digital-WhatsAppOutboundTable',
    MEDIA_BUCKET: 'app.wecare.digital',
    LOG_LEVEL: 'INFO',
  },
});
