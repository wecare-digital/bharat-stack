import { defineFunction } from '@aws-amplify/backend';

/**
 * Wix Store Integration Lambda Function
 * 
 * Purpose: Proxy to Wix Stores REST API + Velo HTTP Functions for products, orders, inventory.
 * Auth: Wix API Key + Site ID for REST API; API Key header for Velo HTTP Functions.
 * 
 * Supports two modes (controlled by WIX_MODE env var):
 *   - 'api'  (default): Uses Wix REST API (wixapis.com)
 *   - 'velo': Uses Velo HTTP Functions on your Wix site (yoursite.com/_functions/*)
 * 
 * Velo mode is useful for accessing custom order numbers and custom fields
 * that are only available through Wix Data collections.
 */
export const wixStore = defineFunction({
  name: 'wecare-wix-store',
  entry: './handler.py',
  runtime: 20, // Python 3.12
  timeoutSeconds: 60,
  memoryMB: 256,
  environment: {
    AWS_REGION: 'us-east-1',
    LOG_LEVEL: 'INFO',
    // Mode: 'api' (Wix REST API) or 'velo' (Velo HTTP Functions)
    WIX_MODE: process.env.WIX_MODE || 'api',
    // Wix REST API config
    WIX_API_KEY: process.env.WIX_API_KEY || '',
    WIX_SITE_ID: process.env.WIX_SITE_ID || '',
    WIX_ACCOUNT_ID: process.env.WIX_ACCOUNT_ID || '6b2d7a93-ef14-45ab-a04e-d445f599e9f4',
    WIX_API_BASE_URL: 'https://www.wixapis.com',
    // Velo HTTP Functions config — set to your published Wix site URL
    WIX_VELO_BASE_URL: process.env.WIX_VELO_BASE_URL || '',  // e.g. https://www.yoursite.com
    WIX_VELO_API_KEY: process.env.WIX_VELO_API_KEY || '',     // Optional: shared secret for Velo auth
    // DynamoDB cache
    WIX_PRODUCTS_CACHE_TABLE: 'base-wecare-digital-WixProductsCache',
    WIX_ORDERS_CACHE_TABLE: 'base-wecare-digital-WixOrdersCache',
    CONTACTS_TABLE: 'base-wecare-digital-ContactsTable',
  },
});
