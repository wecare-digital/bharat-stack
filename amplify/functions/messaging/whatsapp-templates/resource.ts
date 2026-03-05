import { defineFunction } from '@aws-amplify/backend';

/**
 * WhatsApp Templates Lambda (AWS Social Messaging API)
 *
 * Manages WhatsApp message templates via the AWS End User Messaging
 * Social API (socialmessaging client). Supports listing, creating,
 * deleting templates and browsing the Meta template library.
 */
export const whatsappTemplates = defineFunction({
  name: 'wecare-whatsapp-templates',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    MEDIA_BUCKET: 'app.wecare.digital',
    TEMPLATE_MEDIA_PREFIX: 'base/whatsapp-media/template-headers/',
  },
});
