import { defineStorage } from '@aws-amplify/backend';

/**
 * Storage Configuration
 * 
 * Single bucket: app.wecare.digital
 * 
 * Structure:
 * - whatsapp-media/whatsapp-media-incoming/: Inbound WhatsApp media
 * - whatsapp-media/whatsapp-media-outgoing/: Outbound WhatsApp media
 * - stream/: Bulk job reports and exports
 */
export const storage = defineStorage({
  name: 'wecare-media',
  // Reference consolidated bucket: app.wecare.digital
  access: (allow) => ({
    // WhatsApp media paths
    'whatsapp-media/whatsapp-media-incoming/*': [
      allow.authenticated.to(['read', 'write']),
    ],
    'whatsapp-media/whatsapp-media-outgoing/*': [
      allow.authenticated.to(['read', 'write']),
    ],
    // Reports folder
    'stream/*': [
      allow.authenticated.to(['read', 'write']),
    ],
  }),
});

/**
 * SQS Queue Configuration
 * 
 * 4 Queues to be created:
 * 1. inbound-dlq: Failed inbound message processing
 * 2. bulk-queue: Bulk message job processing
 * 3. bulk-dlq: Failed bulk message chunks
 * 4. outbound-dlq: Failed outbound messages
 * 
 * Note: SQS queues are defined via CDK in backend.ts custom resources
 */
export const queueConfig = {
  inboundDlq: {
    name: 'base-wecare-digital-inbound-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
  bulkQueue: {
    name: 'base-wecare-digital-bulk-queue',
    visibilityTimeout: 300,
    messageRetentionPeriod: 86400, // 1 day
  },
  bulkDlq: {
    name: 'base-wecare-digital-bulk-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
  outboundDlq: {
    name: 'base-wecare-digital-outbound-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
};
