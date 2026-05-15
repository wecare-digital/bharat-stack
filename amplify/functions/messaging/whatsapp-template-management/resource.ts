/**
 * WhatsApp Template Management Lambda Function
 * 
 * Full template lifecycle management via Meta Graph API:
 * - CreateWhatsAppMessageTemplate - Create custom template
 * - CreateWhatsAppMessageTemplateMedia - Upload header images/videos
 * - UpdateWhatsAppMessageTemplate - Edit existing template
 * - DeleteWhatsAppMessageTemplate - Delete template
 * - CreateCarouselTemplate - Multi-card carousel templates
 * 
 * API Route: /whatsapp/template-mgmt
 * 
 * Template-creation media (header images/videos/docs) is stored in:
 *   s3://app.wecare.digital/stack/whatsapp-media/template-headers/
 */

import { defineFunction } from '@aws-amplify/backend';

export const whatsappTemplateManagement = defineFunction( {
  name: 'wecare-whatsapp-template-management',
  entry: './handler.py',
  runtime: 20,  // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    LOG_LEVEL: 'INFO',
    MEDIA_BUCKET: 'app.wecare.digital',
    TEMPLATE_MEDIA_PREFIX: 'stack/whatsapp-media/template-headers/',
  },
} );
