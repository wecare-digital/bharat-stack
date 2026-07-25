import { defineFunction } from '@aws-amplify/backend';
import { SEO_TOOLS_TABLE_NAME } from '../../../seo-resources';

/** Admin-only SEO audit and exact blog mutation service. */
export const seoTools = defineFunction( {
    name: 'wecare-seo-tools',
    entry: './handler.py',
    runtime: 20,
    timeoutSeconds: 120,
    memoryMB: 512,
    environment: {
        LOG_LEVEL: 'INFO',
        SEO_TOOLS_TABLE: SEO_TOOLS_TABLE_NAME,
        WEBHOOK_DEDUP_TABLE: 'stack-wecare-digital-WebhookDedup',
        WIX_API_KEY_SECRET: 'wecare/wix-api-key',
        WIX_SITE_ID: '461dece3-613a-42b3-a30c-ed9256898e78',
        BEDROCK_MODEL_ID: process.env.BEDROCK_MODEL_ID || 'global.anthropic.claude-sonnet-4-6',
    },
} );
