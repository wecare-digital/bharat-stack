import { defineFunction } from '@aws-amplify/backend';

export const inboundWhatsappHandler = defineFunction({
  name: 'wecare-inbound-whatsapp',
  entry: './handler.py',
  runtime: 20,
  timeoutSeconds: 120, // Increased for multimodal AI processing
  memoryMB: 512,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    SEND_MODE: 'LIVE',
    CONTACTS_TABLE: 'stack-wecare-digital-ContactsTable',
    MESSAGES_TABLE: 'stack-wecare-digital-WhatsAppInboundTable',
    OUTBOUND_TABLE: 'stack-wecare-digital-WhatsAppOutboundTable',
    MEDIA_FILES_TABLE: 'stack-wecare-digital-MediaFilesTable',
    SYSTEM_CONFIG_TABLE: 'stack-wecare-digital-SystemConfigTable',
    AI_INTERACTIONS_TABLE: 'stack-wecare-digital-AIInteractionsTable',
    MEDIA_BUCKET: 'app.wecare.digital',
    S3_BUCKET: 'app.wecare.digital',
    MEDIA_INBOUND_PREFIX: 'stack/whatsapp-media/incoming/',
    SNS_TOPIC_ARN: `arn:aws:sns:us-east-1:${process.env.AWS_ACCOUNT_ID || '775261844268'}:stack-wecare-digital`,
    INBOUND_DLQ_URL: `https://sqs.us-east-1.amazonaws.com/${process.env.AWS_ACCOUNT_ID || '775261844268'}/stack-wecare-digital-inbound-dlq`,
    OUTBOUND_WHATSAPP_FUNCTION: 'wecare-outbound-whatsapp',
    AI_QUERY_KB_FUNCTION: 'wecare-ai-query-kb',
    AI_GENERATE_RESPONSE_FUNCTION: 'wecare-ai-generate-response',
    WHATSAPP_PHONE_NUMBER_ID_1: 'phone-number-id-5e020cecd221429996f6ae721cc42206',
    WHATSAPP_PHONE_NUMBER_ID_2: 'phone-number-id-waba-t-direct-1055232054343117',
    SUBMIT_REQUESTS_TABLE: 'stack-wecare-digital-SubmitRequestsTable',
  },
});
