import { defineFunction } from '@aws-amplify/backend';

/**
 * WhatsApp Templates Lambda (Meta Graph API)
 *
 * Manages WhatsApp message templates via the Meta Graph API.
 * Supports listing, creating, deleting templates.
 * 
 * API Route: /whatsapp/templates
 * 
 * Template-creation media (header images/videos/docs) is stored in:
 *   s3://app.wecare.digital/stack/whatsapp-media/template-headers/
 * 
 * Template-send media (public, WhatsApp fetches via URL) is stored in:
 *   s3://app.wecare.digital/public/wa-tpl/{docs|img|vid|aud|stk}/
 */
export const whatsappTemplates = defineFunction( {
  name: 'wecare-whatsapp-templates',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    MEDIA_BUCKET: 'app.wecare.digital',
    TEMPLATE_MEDIA_PREFIX: 'stack/whatsapp-media/template-headers/',
  },
} );
