/**
 * Push Notifications Lambda - WECARE.DIGITAL
 *
 * Handles:
 * - POST /push/register   — Register device token (FCM / APNs)
 * - POST /push/send       — Send push to a device or topic
 * - DELETE /push/register  — Unregister device token
 *
 * AWS Resources required:
 * - SNS Platform Application (FCM): stack-wecare-push-android
 * - SNS Platform Application (APNs): stack-wecare-push-ios
 * - DynamoDB Table: PushTokensTable (deviceToken PK, userId SK)
 */
import { defineFunction } from '@aws-amplify/backend';

export const pushNotifications = defineFunction( {
  name: 'push-notifications',
  entry: './handler.py',
  runtime: 20,  // Python 3.12
  timeoutSeconds: 30,
  memoryMB: 256,
  environment: {
    SNS_PLATFORM_APP_ARN_ANDROID: process.env.SNS_PLATFORM_APP_ARN_ANDROID || '',
    SNS_PLATFORM_APP_ARN_IOS: process.env.SNS_PLATFORM_APP_ARN_IOS || '',
    PUSH_TOKENS_TABLE: process.env.PUSH_TOKENS_TABLE || 'stack-wecare-digital-PushTokensTable',
  },
} );
