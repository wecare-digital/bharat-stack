import { defineStorage } from '@aws-amplify/backend';

/**
 * Storage Configuration
 * 
 * Single bucket: app.wecare.digital
 * 
 * Structure:
 * - stack/              : All user/transactional data (factory reset = wipe stack/ only)
 *   - whatsapp-media/  : incoming/, outgoing/, voice/, calling-ai/, template-headers/, downloads/
 *   - invoices/        : Invoice PNGs and PDFs
 *   - voice/           : Voice recordings (Airtel OBD)
 *   - reports/         : Bulk job reports and exports
 *   - store/products/  : Product images
 * - stream/            : Static internal assets (NEVER wiped)
 *   - media/m/         : Logos, branding images
 *   - media/fonts/     : Invoice PDF fonts
 *   - media/ivr/       : IVR audio files
 */
export const storage = defineStorage({
  name: 'wecare-media',
  // Reference consolidated bucket: app.wecare.digital
  access: (allow) => ({
    // User/transactional data — all under stack/
    'stack/*': [
      allow.authenticated.to(['read', 'write']),
    ],
    // Static internal assets — read-only for authenticated users
    'stream/*': [
      allow.authenticated.to(['read']),
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
    name: 'stack-wecare-digital-inbound-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
  bulkQueue: {
    name: 'stack-wecare-digital-bulk-queue',
    visibilityTimeout: 300,
    messageRetentionPeriod: 86400, // 1 day
  },
  bulkDlq: {
    name: 'stack-wecare-digital-bulk-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
  outboundDlq: {
    name: 'stack-wecare-digital-outbound-dlq',
    visibilityTimeout: 300,
    messageRetentionPeriod: 604800, // 7 days
  },
};
