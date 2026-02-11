/**
 * WhatsApp Template Management Lambda Function Resource
 * 
 * Full template lifecycle management via AWS EUM Social API:
 * - CreateWhatsAppMessageTemplate - Create custom template
 * - CreateWhatsAppMessageTemplateFromLibrary - Create from Meta library
 * - CreateWhatsAppMessageTemplateMedia - Upload header images
 * - UpdateWhatsAppMessageTemplate - Edit existing template
 * - DeleteWhatsAppMessageTemplate - Delete template
 * - ListWhatsAppTemplateLibrary - Browse Meta's pre-built templates
 */

import { defineFunction } from '@aws-amplify/backend';

export const whatsappTemplateManagement = defineFunction({
  name: 'wecare-whatsapp-template-management',
  entry: './handler.py',
  runtime: 20,  // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 512,
  environment: {
    LOG_LEVEL: 'INFO',
    MEDIA_BUCKET: 'app.wecare.digital',
    TEMPLATE_MEDIA_PREFIX: 'whatsapp-media/template-headers/',
  },
});
